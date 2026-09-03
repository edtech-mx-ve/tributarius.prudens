from __future__ import annotations

from app.domain.query import (
    QueryAnalysis,
    QueryDimensionName,
    QueryTaxonomyBasis,
    QueryTemporalSignalKind,
)
from llm.providers.runtime_query import RuntimeQueryAnalyzerProvider
from llm.query_analyzer import QueryAnalyzer


def _analyze(query: str) -> QueryAnalysis:
    return QueryAnalyzer(RuntimeQueryAnalyzerProvider()).analyze(query)


def _dimension_values(result: QueryAnalysis, name: QueryDimensionName) -> set[str]:
    multidimensional = result.multidimensional
    assert multidimensional is not None
    return {
        item.value
        for item in multidimensional.dimensions
        if item.dimension is name
    }


def test_d1_extracts_factual_and_semantic_dimensions_for_isr() -> None:
    result = _analyze(
        "Soy persona física y presto servicios profesionales; "
        "quiero calcular ISR del ejercicio 2025."
    )
    multidimensional = result.multidimensional
    assert multidimensional is not None

    assert _dimension_values(result, QueryDimensionName.TAXPAYER_TYPE) == {"individual"}
    assert _dimension_values(result, QueryDimensionName.ACTIVITY) == {
        "servicios profesionales independientes"
    }
    assert _dimension_values(result, QueryDimensionName.TAX) == {"ISR"}
    assert _dimension_values(result, QueryDimensionName.FISCAL_YEAR) == {"2025"}
    assert multidimensional.primary_problem_id == "determinacion_contribucion"
    assert multidimensional.primary_institution_id == "regimen_isr"
    assert multidimensional.unresolved_dimensions == []
    assert any(
        item.kind is QueryTemporalSignalKind.EXPLICIT_YEAR and item.value == "2025"
        for item in multidimensional.temporal_signals
    )


def test_d1_uses_a6_text_and_intent_without_producing_legal_decision() -> None:
    result = _analyze(
        "El SAT me notificó un crédito fiscal y quiero impugnarlo mediante una defensa en 2026."
    )
    multidimensional = result.multidimensional
    assert multidimensional is not None

    assert multidimensional.primary_problem_id == "defensa_contribuyente"
    assert {item.concept_id for item in multidimensional.institution_matches} >= {
        "deuda_tributaria",
        "derechos_contribuyente",
    }
    debt = next(
        item
        for item in multidimensional.institution_matches
        if item.concept_id == "deuda_tributaria"
    )
    assert debt.basis is QueryTaxonomyBasis.TAXONOMY_TEXT
    assert multidimensional.downstream_activation_enabled is False
    assert multidimensional.can_control_legal_decision is False


def test_d1_recognizes_resico_as_regime_signal_without_activating_downstream() -> None:
    result = _analyze(
        "Soy persona física en RESICO y quiero conocer mis obligaciones fiscales para 2026."
    )
    multidimensional = result.multidimensional
    assert multidimensional is not None

    assert _dimension_values(result, QueryDimensionName.FISCAL_REGIME) == {"RESICO"}
    assert multidimensional.primary_problem_id == "cumplimiento_fiscal"
    assert {item.concept_id for item in multidimensional.institution_matches} >= {
        "obligacion_tributaria",
        "regimen_isr",
    }
    assert multidimensional.requires_temporal_validation is True
    assert multidimensional.downstream_activation_enabled is False


def test_d1_marks_rif_as_historical_context_but_does_not_decide_applicability() -> None:
    result = _analyze("¿Cómo calculaba ISR una persona física en RIF durante 2020?")
    multidimensional = result.multidimensional
    assert multidimensional is not None

    assert _dimension_values(result, QueryDimensionName.FISCAL_REGIME) == {"RIF"}
    assert any(
        item.kind is QueryTemporalSignalKind.HISTORICAL_CONTEXT
        for item in multidimensional.temporal_signals
    )
    assert multidimensional.requires_temporal_validation is True
    assert multidimensional.can_control_legal_decision is False


def test_d1_supports_multi_issue_queries_without_collapsing_dimensions() -> None:
    result = _analyze(
        "Como persona física quiero conocer mis obligaciones fiscales "
        "y mis derechos fiscales en 2026."
    )
    multidimensional = result.multidimensional
    assert multidimensional is not None

    institution_ids = {item.concept_id for item in multidimensional.institution_matches}
    assert "obligacion_tributaria" in institution_ids
    assert "derechos_contribuyente" in institution_ids
    assert multidimensional.semantic_issue_count >= 3


def test_d1_does_not_invent_dimensions_for_unknown_query() -> None:
    result = _analyze("Necesito orientación sobre un asunto que no he descrito todavía.")
    multidimensional = result.multidimensional
    assert multidimensional is not None

    assert multidimensional.dimensions == []
    assert multidimensional.problem_matches == []
    assert multidimensional.institution_matches == []
    assert multidimensional.temporal_signals == []
    assert multidimensional.requires_temporal_validation is False
    assert multidimensional.can_control_legal_decision is False
