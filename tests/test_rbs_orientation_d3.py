from __future__ import annotations

from app.domain.primary_rbs_decision_boundary import PrimaryRBSDecisionRole
from app.domain.query import QueryAnalysis, RBSOrientationIntegration
from app.services.rbs_orientation import (
    load_default_existing_rbs_integration,
    load_default_primary_rbs_boundary,
    load_default_primary_rbs_corpus_validation,
    load_default_primary_rbs_deduplication,
)
from llm.providers.runtime_query import RuntimeQueryAnalyzerProvider
from llm.query_analyzer import QueryAnalyzer


def _analyze(query: str) -> QueryAnalysis:
    return QueryAnalyzer(RuntimeQueryAnalyzerProvider()).analyze(query)


def _orientation(query: str) -> RBSOrientationIntegration:
    result = _analyze(query)
    assert result.multidimensional is not None
    assert result.primary_source_activation is not None
    assert result.primary_source_activation.rbs_activation_enabled is False
    assert result.rbs_orientation is not None
    return result.rbs_orientation


def test_d3_professional_isr_prioritizes_specialized_primary_rbs_relation() -> None:
    orientation = _orientation(
        "Soy persona física y presto servicios profesionales; "
        "quiero calcular ISR del ejercicio 2025."
    )
    relations = {item.relation_id: item for item in orientation.relations}

    assert orientation.relations[0].relation_id == "B5-REL-017"
    assert orientation.relations[0].score == 1.0
    assert {"B5-REL-006", "B5-REL-009", "B5-REL-017"} <= set(relations)
    professional = relations["B5-REL-017"]
    assert professional.role is PrimaryRBSDecisionRole.DETERMINATION_CANDIDATE
    assert professional.exact_normative_refs == ["lisr:articulo_100"]
    assert professional.linked_existing_rule_ids == ["ISR_PROFESSIONAL_CLASSIFY_001"]
    assert professional.orientation_only is True
    assert professional.executable_determination_enabled is False


def test_d3_defense_routes_to_authority_debt_and_defense_relations_without_execution() -> None:
    orientation = _orientation(
        "El SAT me notificó un crédito fiscal y quiero impugnarlo "
        "mediante una defensa en 2026."
    )
    relations = {item.relation_id: item for item in orientation.relations}

    assert {"B5-REL-010", "B5-REL-011", "B5-REL-012"} <= set(relations)
    defense = relations["B5-REL-012"]
    assert defense.role is PrimaryRBSDecisionRole.DETERMINATION_CANDIDATE
    assert defense.exact_normative_refs == ["lfdc:articulo_2"]
    assert defense.determination_ready is False
    assert orientation.production_rule_execution_enabled is False
    assert orientation.reuse_existing_rule_engine is True


def test_d3_explicit_rif_prioritizes_temporal_relation_but_keeps_it_non_determinative() -> None:
    orientation = _orientation("¿Cómo calculaba ISR una persona física en RIF durante 2020?")

    assert orientation.relations[0].relation_id == "B5-REL-018"
    temporal = orientation.relations[0]
    assert temporal.score == 1.0
    assert temporal.role is PrimaryRBSDecisionRole.ORIENTATION
    assert temporal.exact_normative_refs == []
    assert temporal.matched_primary_entry_ids == ["PRODECON-12"]
    assert "R-TEM" in temporal.rbs_family_ids
    assert orientation.requires_temporal_validation is True
    assert temporal.temporal_applicability_confirmed is False


def test_d3_resico_never_activates_rif_temporal_relation() -> None:
    orientation = _orientation(
        "Soy persona física en RESICO y quiero conocer mis obligaciones fiscales para 2026."
    )
    ids = {item.relation_id for item in orientation.relations}

    assert "B5-REL-018" not in ids
    assert orientation.activation_applied is True
    assert orientation.requires_temporal_validation is True


def test_d3_unknown_query_does_not_invent_rbs_orientation() -> None:
    result = _analyze("Necesito orientación sobre un asunto que no he descrito todavía.")
    assert result.primary_source_activation is not None
    orientation = result.rbs_orientation
    assert orientation is not None

    assert result.primary_source_activation.activation_applied is False
    assert orientation.activation_applied is False
    assert orientation.relations == []
    assert orientation.activated_relation_count == 0
    assert orientation.candidate_normative_sources == []
    assert orientation.requires_temporal_validation is False
    assert len(orientation.normative_corpus_ids) == 12
    assert orientation.full_normative_corpus_preserved is True


def test_d3_uses_exact_b5_b7_b8_contract_and_b9_only_as_non_executed_bridge() -> None:
    orientation = _orientation(
        "Soy persona física y quiero conocer mis derechos fiscales y obligaciones en 2026."
    )
    deduplication = load_default_primary_rbs_deduplication()
    boundaries = load_default_primary_rbs_boundary()
    corpus = load_default_primary_rbs_corpus_validation()
    integrations = load_default_existing_rbs_integration()

    known_relations = {item.canonical_id for item in deduplication.relations}
    boundary_by_relation = {item.relation_id: item for item in boundaries.boundaries}
    validation_by_relation = {item.relation_id: item for item in corpus.relation_validations}
    known_rules = {item.rule_id for item in integrations.integrations}

    assert len(known_relations) == 18
    assert integrations.total_rules == 14
    assert orientation.available_primary_relation_count == 18
    assert orientation.available_existing_rule_count == 14
    assert {item.relation_id for item in orientation.relations} <= known_relations
    assert set(orientation.linked_existing_rule_ids) <= known_rules

    for item in orientation.relations:
        boundary = boundary_by_relation[item.relation_id]
        validation = validation_by_relation[item.relation_id]
        assert item.role is boundary.role
        assert item.normative_source_ids == boundary.normative_source_ids
        assert item.exact_normative_refs == boundary.exact_normative_refs
        assert item.corpus_validation_status is validation.status
        assert item.blocked_normative_sources == validation.blocked_normative_sources
        assert item.requires_case_date_validation is True
        assert item.temporal_applicability_confirmed is False
        assert item.determination_ready is False
        assert item.orientation_only is True


def test_d3_preserves_closed_evidence_and_does_not_advance_d4_d5_or_d7() -> None:
    result = _analyze(
        "Soy persona física y presto servicios profesionales; "
        "quiero calcular ISR del ejercicio 2025."
    )
    activation = result.primary_source_activation
    orientation = result.rbs_orientation
    assert activation is not None
    assert orientation is not None

    assert orientation.activation_applied is True
    assert orientation.requires_normative_validation is True
    assert orientation.full_normative_corpus_preserved is True
    assert orientation.normative_corpus_ids == activation.normative_corpus_ids
    assert set(orientation.candidate_normative_sources) <= set(orientation.normative_corpus_ids)
    assert orientation.reuse_existing_rule_engine is True
    assert orientation.production_rule_execution_enabled is False
    assert orientation.normative_ranking_enabled is False
    assert orientation.cbr_activation_enabled is False
    assert orientation.rag_retrieval_enabled is False
    assert orientation.can_control_legal_decision is False
    assert all(item.can_control_legal_decision is False for item in orientation.relations)
