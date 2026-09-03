from __future__ import annotations

from app.domain.primary_cbr_levels import PrimaryCBRKnowledgeLevel
from app.domain.query import CBROrientationIntegration, QueryAnalysis
from app.services.cbr_orientation import (
    load_default_primary_cbr_legal_similarity,
    load_default_primary_cbr_levels,
)
from llm.providers.runtime_query import RuntimeQueryAnalyzerProvider
from llm.query_analyzer import QueryAnalyzer


def _analyze(query: str) -> QueryAnalysis:
    return QueryAnalyzer(RuntimeQueryAnalyzerProvider()).analyze(query)


def _orientation(query: str) -> CBROrientationIntegration:
    result = _analyze(query)
    assert result.multidimensional is not None
    assert result.primary_source_activation is not None
    assert result.rbs_orientation is not None
    assert result.rbs_orientation.cbr_activation_enabled is False
    assert result.cbr_orientation is not None
    return result.cbr_orientation


def test_d4_professional_isr_reuses_c9_similarity_and_surfaces_nearest_cases() -> None:
    orientation = _orientation(
        "Soy persona física y presto servicios profesionales; "
        "quiero calcular ISR del ejercicio 2025."
    )

    assert orientation.query_primary_family_id == "CBR-CALCULO"
    assert orientation.matches[0].situation_id == "U-CBR-SIT-009"
    assert orientation.matches[0].similarity == 1.0
    assert orientation.matches[0].knowledge_level is PrimaryCBRKnowledgeLevel.VALIDATED
    assert orientation.matches[0].validated_normative_refs == ["lisr:articulo_106"]
    assert "P-CBR-SIT-009" in {item.situation_id for item in orientation.matches}
    assert orientation.reuse_existing_cbr_similarity is True


def test_d4_resico_uses_obligation_family_without_reactivating_rif_cases() -> None:
    orientation = _orientation(
        "Soy persona física en RESICO y quiero conocer mis obligaciones fiscales para 2026."
    )

    assert orientation.query_primary_family_id == "CBR-OBLIGACION"
    assert orientation.activation_applied is True
    assert all(item.historical_regime_context is False for item in orientation.matches)
    assert not {"P-CBR-SIT-023", "P-CBR-SIT-024", "U-CBR-SIT-008"} & {
        item.situation_id for item in orientation.matches
    }
    assert orientation.requires_temporal_validation is True


def test_d4_rif_stays_inside_historical_context_and_never_becomes_operational() -> None:
    orientation = _orientation("¿Cómo calculaba ISR una persona física en RIF durante 2020?")

    assert orientation.query_historical_context is True
    assert [item.situation_id for item in orientation.matches] == [
        "P-CBR-SIT-023",
        "P-CBR-SIT-024",
        "U-CBR-SIT-008",
    ]
    assert all(item.historical_regime_context for item in orientation.matches)
    assert all(
        item.knowledge_level is PrimaryCBRKnowledgeLevel.PRIMARY
        for item in orientation.matches
    )
    assert all(item.requires_normative_review for item in orientation.matches)
    assert all(item.operational_reuse_allowed is False for item in orientation.matches)
    assert orientation.candidate_normative_sources == []


def test_d4_does_not_force_analogy_when_relevant_family_stays_below_threshold() -> None:
    orientation = _orientation(
        "El SAT me notificó un crédito fiscal y quiero impugnarlo "
        "mediante una defensa en 2026."
    )

    assert orientation.query_primary_family_id == "CBR-DEFENSA"
    assert orientation.candidate_count == 2
    assert orientation.activation_applied is False
    assert orientation.returned_count == 0
    assert orientation.matches == []


def test_d4_unknown_query_does_not_invent_cbr_profile_or_narrow_corpus() -> None:
    orientation = _orientation(
        "Necesito orientación sobre un asunto que no he descrito todavía."
    )

    assert orientation.query_primary_family_id is None
    assert orientation.query_family_ids == []
    assert orientation.query_concept_ids == []
    assert orientation.candidate_count == 0
    assert orientation.matches == []
    assert orientation.activation_applied is False
    assert len(orientation.normative_corpus_ids) == 12
    assert orientation.full_normative_corpus_preserved is True


def test_d4_consumes_exact_c9_profiles_and_c10_levels_without_operational_cases() -> None:
    orientation = _orientation(
        "Soy persona física y presto servicios profesionales; "
        "quiero calcular ISR del ejercicio 2025."
    )
    similarity = load_default_primary_cbr_legal_similarity()
    levels = load_default_primary_cbr_levels()
    known_profile_ids = {item.situation_id for item in similarity.profiles}
    levels_by_id = {item.situation_id: item for item in levels.assessments}

    assert similarity.profile_count == 37
    assert levels.primary_membership_count == 37
    assert levels.validated_membership_count == 20
    assert levels.operational_membership_count == 0
    assert orientation.available_primary_profile_count == 37
    assert orientation.available_validated_profile_count == 20
    assert orientation.available_operational_case_count == 0
    assert {item.situation_id for item in orientation.matches} <= known_profile_ids
    for item in orientation.matches:
        assert item.knowledge_level is levels_by_id[item.situation_id].highest_level
        assert item.operational_reuse_allowed is False


def test_d4_preserves_closed_evidence_and_does_not_advance_d5_or_d7() -> None:
    result = _analyze(
        "Soy persona física y presto servicios profesionales; "
        "quiero calcular ISR del ejercicio 2025."
    )
    activation = result.primary_source_activation
    rbs = result.rbs_orientation
    orientation = result.cbr_orientation
    assert activation is not None
    assert rbs is not None
    assert orientation is not None

    assert orientation.normative_corpus_ids == activation.normative_corpus_ids
    assert orientation.normative_corpus_ids == rbs.normative_corpus_ids
    assert set(orientation.candidate_normative_sources) <= set(
        orientation.normative_corpus_ids
    )
    assert orientation.requires_normative_validation is True
    assert orientation.reuse_existing_cbr_similarity is True
    assert orientation.uses_primary_cbr_profiles is True
    assert orientation.uses_operational_cbr_cases is False
    assert orientation.operational_reuse_enabled is False
    assert orientation.normative_ranking_enabled is False
    assert orientation.rag_retrieval_enabled is False
    assert orientation.can_control_legal_decision is False
    assert all(item.orientation_only for item in orientation.matches)
    assert all(item.can_control_legal_decision is False for item in orientation.matches)
