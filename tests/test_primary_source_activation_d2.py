from __future__ import annotations

from app.domain.primary_legal_knowledge import PrimaryManual
from app.domain.query import PrimarySourceActivation, QueryAnalysis
from app.services.primary_source_activation import (
    load_default_primary_knowledge_manifest,
    load_default_primary_knowledge_map,
)
from llm.providers.runtime_query import RuntimeQueryAnalyzerProvider
from llm.query_analyzer import QueryAnalyzer


def _analyze(query: str) -> QueryAnalysis:
    return QueryAnalyzer(RuntimeQueryAnalyzerProvider()).analyze(query)


def _activation(query: str) -> PrimarySourceActivation:
    result = _analyze(query)
    assert result.multidimensional is not None
    assert result.multidimensional.downstream_activation_enabled is False
    assert result.primary_source_activation is not None
    return result.primary_source_activation


def test_d2_activates_focused_prodecon_unam_for_professional_isr() -> None:
    activation = _activation(
        "Soy persona física y presto servicios profesionales; "
        "quiero calcular ISR del ejercicio 2025."
    )
    entries = {item.entry_id: item for item in activation.entries}

    assert {"PRODECON-05", "PRODECON-11", "UNAM-V"} <= set(entries)
    assert entries["PRODECON-11"].score == 1.0
    assert entries["UNAM-V"].score == 1.0
    assert "PRODECON-10" not in entries
    assert "PRODECON-12" not in entries
    assert {"PRODECON-10", "PRODECON-12"} <= set(activation.suppressed_entry_ids)
    assert activation.prodecon_count > 0
    assert activation.unam_count > 0


def test_d2_resico_does_not_activate_historical_rif_entry() -> None:
    activation = _activation(
        "Soy persona física en RESICO y quiero conocer mis obligaciones fiscales para 2026."
    )
    ids = {item.entry_id for item in activation.entries}

    assert "PRODECON-05" in ids
    assert "UNAM-V" in ids
    assert "PRODECON-12" not in ids
    assert not any(item.historical_content for item in activation.entries)
    assert activation.requires_temporal_validation is True


def test_d2_rif_explicitly_unlocks_historical_navigation_only() -> None:
    activation = _activation("¿Cómo calculaba ISR una persona física en RIF durante 2020?")
    entries = {item.entry_id: item for item in activation.entries}

    assert "PRODECON-12" in entries
    assert entries["PRODECON-12"].historical_content is True
    assert entries["PRODECON-12"].requires_temporal_validation is True
    assert "PRODECON-10" not in entries
    assert "PRODECON-11" not in entries
    assert {"PRODECON-10", "PRODECON-11"} <= set(activation.suppressed_entry_ids)
    assert activation.requires_temporal_validation is True


def test_d2_activates_defense_and_debt_navigation_in_both_manuals() -> None:
    activation = _activation(
        "El SAT me notificó un crédito fiscal y quiero impugnarlo "
        "mediante una defensa en 2026."
    )
    ids = {item.entry_id for item in activation.entries}

    assert {"PRODECON-06", "PRODECON-08", "UNAM-VI", "UNAM-VII"} <= ids
    assert activation.candidate_normative_hints == ["cff", "lfdc", "lfpca", "lotfja"]


def test_d2_unknown_query_keeps_corpus_available_without_false_activation() -> None:
    activation = _activation(
        "Necesito orientación sobre un asunto que no he descrito todavía."
    )
    manifest = load_default_primary_knowledge_manifest()

    assert activation.activation_applied is False
    assert activation.entries == []
    assert activation.candidate_normative_hints == []
    assert activation.normative_corpus_ids == manifest.normative_corpus_ids
    assert activation.full_normative_corpus_preserved is True


def test_d2_uses_only_registered_primary_entries_and_all_twelve_normative_corpora() -> None:
    activation = _activation(
        "Soy persona física y presto servicios profesionales; "
        "quiero calcular ISR del ejercicio 2025."
    )
    knowledge_map = load_default_primary_knowledge_map()
    manifest = load_default_primary_knowledge_manifest()
    known_entries = {item.entry_id for item in knowledge_map.entries}

    assert len(knowledge_map.entries) == 19
    assert len(manifest.normative_corpus_ids) == 12
    assert {item.entry_id for item in activation.entries} <= known_entries
    assert set(activation.candidate_normative_hints) <= set(manifest.normative_corpus_ids)
    assert activation.normative_corpus_ids == manifest.normative_corpus_ids
    assert {item.manual for item in activation.entries} == {
        PrimaryManual.PRODECON,
        PrimaryManual.UNAM,
    }


def test_d2_preserves_orientation_boundary_and_does_not_advance_later_stages() -> None:
    activation = _activation(
        "Soy persona física y quiero conocer mis derechos fiscales y obligaciones en 2026."
    )

    assert activation.activation_applied is True
    assert activation.requires_normative_validation is True
    assert activation.full_normative_corpus_preserved is True
    assert activation.normative_ranking_enabled is False
    assert activation.rbs_activation_enabled is False
    assert activation.cbr_activation_enabled is False
    assert activation.rag_retrieval_enabled is False
    assert activation.can_control_legal_decision is False
    assert all(item.requires_normative_validation for item in activation.entries)
    assert all(item.can_control_legal_decision is False for item in activation.entries)
