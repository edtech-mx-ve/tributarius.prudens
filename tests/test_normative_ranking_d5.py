from __future__ import annotations

from app.domain.query import NormativeRankingIntegration, NormativeRankingTier, QueryAnalysis
from app.services.normative_ranking import (
    load_default_normative_corpus_ids,
    load_default_normative_ranking_policy,
)
from llm.providers.runtime_query import RuntimeQueryAnalyzerProvider
from llm.query_analyzer import QueryAnalyzer


def _analyze(query: str) -> QueryAnalysis:
    return QueryAnalyzer(RuntimeQueryAnalyzerProvider()).analyze(query)


def _ranking(query: str) -> NormativeRankingIntegration:
    result = _analyze(query)
    assert result.multidimensional is not None
    assert result.primary_source_activation is not None
    assert result.rbs_orientation is not None
    assert result.cbr_orientation is not None
    assert result.normative_ranking is not None
    return result.normative_ranking


def test_d5_professional_isr_prioritizes_isr_sources_and_demotes_other_tax_statutes() -> None:
    ranking = _ranking(
        "Soy persona física y presto servicios profesionales; "
        "quiero calcular ISR del ejercicio 2025."
    )
    by_id = {item.corpus_id: item for item in ranking.ranked_sources}

    assert ranking.query_tax == "ISR"
    assert ranking.ranked_sources[0].corpus_id == "lisr"
    assert ranking.ranked_sources[0].relevance_score == 1.0
    assert ranking.focus_source_ids[:2] == ["lisr", "cff"]
    assert by_id["lisr"].explicit_tax_compatibility == 1.0
    assert by_id["liva"].explicit_tax_compatibility == 0.1
    assert by_id["lieps"].explicit_tax_compatibility == 0.1
    assert by_id["lfisan"].explicit_tax_compatibility == 0.1
    assert by_id["lisr"].rank < by_id["liva"].rank
    assert "lisr:articulo_100" in by_id["lisr"].exact_normative_refs
    assert "lisr:articulo_106" in by_id["lisr"].exact_normative_refs


def test_d5_resico_ranks_general_obligation_sources_without_reactivating_rif() -> None:
    result = _analyze(
        "Soy persona física en RESICO y quiero conocer mis obligaciones fiscales para 2026."
    )
    ranking = result.normative_ranking
    cbr = result.cbr_orientation
    assert ranking is not None
    assert cbr is not None

    assert ranking.query_tax is None
    assert ranking.focus_source_ids[:3] == ["cff", "lfdc", "lisr"]
    assert ranking.ranking_applied is True
    assert not {"P-CBR-SIT-023", "P-CBR-SIT-024", "U-CBR-SIT-008"} & {
        item.situation_id for item in cbr.matches
    }


def test_d5_historical_rif_preserves_all_sources_and_flags_rbs_temporal_block() -> None:
    ranking = _ranking("¿Cómo calculaba ISR una persona física en RIF durante 2020?")
    by_id = {item.corpus_id: item for item in ranking.ranked_sources}

    assert ranking.query_tax == "ISR"
    assert ranking.ranked_sources[0].corpus_id == "lisr"
    assert len(ranking.ranked_sources) == 12
    assert by_id["liva"].rbs_temporal_block_detected is True
    assert by_id["liva"].requires_temporal_validation is True
    assert ranking.temporal_validation_completed is False
    assert ranking.requires_temporal_validation is True


def test_d5_defense_prioritizes_procedural_sources_and_keeps_exact_validated_hint() -> None:
    ranking = _ranking(
        "El SAT me notificó un crédito fiscal y quiero impugnarlo "
        "mediante una defensa en 2026."
    )
    by_id = {item.corpus_id: item for item in ranking.ranked_sources}

    assert ranking.focus_source_ids == ["cff", "lfdc", "lfpca", "lotfja"]
    assert by_id["cff"].rank == 1
    assert by_id["lfdc"].rank == 2
    assert "lfdc:articulo_2" in by_id["lfdc"].exact_normative_refs
    assert by_id["lfdc"].tier is NormativeRankingTier.FOCAL


def test_d5_unknown_query_preserves_canonical_twelve_without_inventing_priority() -> None:
    ranking = _ranking("Necesito orientación sobre un asunto que no he descrito todavía.")
    corpus_ids = list(load_default_normative_corpus_ids())

    assert ranking.ranking_applied is False
    assert ranking.focus_source_ids == []
    assert [item.corpus_id for item in ranking.ranked_sources] == corpus_ids
    assert [item.rank for item in ranking.ranked_sources] == list(range(1, 13))
    assert all(item.relevance_score == 0 for item in ranking.ranked_sources)
    assert all(item.tier is NormativeRankingTier.EXPANSION for item in ranking.ranked_sources)


def test_d5_uses_exact_a8_space_and_deterministic_weight_contract() -> None:
    ranking = _ranking(
        "Soy persona física y presto servicios profesionales; "
        "quiero calcular ISR del ejercicio 2025."
    )
    policy = load_default_normative_ranking_policy()
    corpus_ids = list(load_default_normative_corpus_ids())

    assert ranking.normative_corpus_ids == corpus_ids
    assert set(item.corpus_id for item in ranking.ranked_sources) == set(corpus_ids)
    assert ranking.component_weights == policy.component_weights
    assert ranking.component_weights == {
        "primary_activation": 0.45,
        "rbs_orientation": 0.35,
        "cbr_orientation": 0.2,
    }
    lisr = ranking.ranked_sources[0]
    expected = (
        lisr.primary_activation_component * 0.45
        + lisr.rbs_orientation_component * 0.35
        + lisr.cbr_orientation_component * 0.2
    ) * lisr.explicit_tax_compatibility
    assert lisr.relevance_score == round(expected, 6)


def test_d5_is_relevance_only_and_does_not_advance_navigation_rag_or_legal_decision() -> None:
    ranking = _ranking(
        "Soy persona física y presto servicios profesionales; "
        "quiero calcular ISR del ejercicio 2025."
    )

    assert ranking.full_normative_corpus_preserved is True
    assert ranking.source_exclusion_enabled is False
    assert ranking.ranking_is_relevance_not_validity is True
    assert ranking.legal_hierarchy_interpreted is False
    assert ranking.requires_normative_validation is True
    assert ranking.requires_temporal_validation is True
    assert ranking.normative_validation_completed is False
    assert ranking.temporal_validation_completed is False
    assert ranking.structural_navigation_enabled is False
    assert ranking.rag_retrieval_enabled is False
    assert ranking.can_control_legal_decision is False
    assert all(item.can_control_legal_decision is False for item in ranking.ranked_sources)
