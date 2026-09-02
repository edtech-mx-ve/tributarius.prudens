from __future__ import annotations

from app.domain.integral_legal_analysis import IntegralLegalAnalysisStatus
from app.domain.integral_legal_readiness import (
    EvidentiarySufficiency,
    LegalCompletenessDimension,
    LegalCompletenessState,
)
from app.domain.orchestration import HybridOrchestrationResult
from app.domain.query import MissingField
from app.services.integral_legal_analyzer import build_integral_legal_analysis
from app.services.integral_legal_readiness import evaluate_integral_legal_readiness
from tests.test_block12_4_hypothesis_verification import _orchestrator, _request


def _result() -> HybridOrchestrationResult:
    return _orchestrator(None).run(_request())


def _state(
    result: HybridOrchestrationResult,
    dimension: LegalCompletenessDimension,
) -> LegalCompletenessState:
    readiness = evaluate_integral_legal_readiness(result)
    return next(
        item.state for item in readiness.completeness if item.dimension == dimension
    )


def test_readiness_is_sufficient_for_complete_deterministic_case() -> None:
    result = _result()
    readiness = evaluate_integral_legal_readiness(result)

    assert readiness.evidentiary_sufficiency == EvidentiarySufficiency.SUFFICIENT
    assert readiness.can_close_automatically is True
    assert readiness.missing_requirements == []


def test_normative_basis_is_required_for_integral_closure() -> None:
    result = _result()
    result.applicable_normative_refs = []

    readiness = evaluate_integral_legal_readiness(result)

    assert (
        _state(result, LegalCompletenessDimension.NORMATIVE_BASIS)
        == LegalCompletenessState.MISSING
    )
    assert readiness.evidentiary_sufficiency == EvidentiarySufficiency.INSUFFICIENT
    assert readiness.can_close_automatically is False


def test_rbs_conclusion_is_required_for_integral_closure() -> None:
    result = _result()
    result.rule_result.matched_rules = []

    readiness = evaluate_integral_legal_readiness(result)

    assert (
        _state(result, LegalCompletenessDimension.RULE_REASONING)
        == LegalCompletenessState.MISSING
    )
    assert readiness.evidentiary_sufficiency == EvidentiarySufficiency.INSUFFICIENT


def test_calculation_is_required_when_primary_intent_is_calculate_isr() -> None:
    result = _result()
    result.isr_result = None

    readiness = evaluate_integral_legal_readiness(result)

    assert (
        _state(result, LegalCompletenessDimension.CALCULATION)
        == LegalCompletenessState.MISSING
    )
    assert readiness.evidentiary_sufficiency == EvidentiarySufficiency.INSUFFICIENT


def test_missing_fields_make_facts_partial_and_require_clarification_context() -> None:
    result = _result()
    result.analysis.missing_fields = [
        MissingField(name="fiscal_year", reason="Falta el ejercicio fiscal.")
    ]
    result.analysis.requires_clarification = True

    readiness = evaluate_integral_legal_readiness(result)

    assert (
        _state(result, LegalCompletenessDimension.FACTS)
        == LegalCompletenessState.PARTIAL
    )
    assert readiness.evidentiary_sufficiency == EvidentiarySufficiency.LIMITED
    assert readiness.requires_clarification is True
    assert "fiscal_year: Falta el ejercicio fiscal." in readiness.missing_requirements


def test_human_review_limits_automatic_closure_without_erasing_evidence() -> None:
    result = _result()
    result.requires_human_review = True

    readiness = evaluate_integral_legal_readiness(result)

    assert readiness.evidentiary_sufficiency == EvidentiarySufficiency.LIMITED
    assert readiness.requires_human_review is True
    assert readiness.can_close_automatically is False


def test_analyzer_1_0_includes_readiness_without_changing_canonical_result() -> None:
    result = _result()
    analysis = build_integral_legal_analysis(result)

    assert analysis.readiness.can_close_automatically is True
    assert analysis.canonical_conclusion == result.rule_result.matched_rules[0].conclusion
    assert analysis.controlling_source == "rbs"
    assert analysis.status == IntegralLegalAnalysisStatus.READY


def test_insufficient_readiness_propagates_to_analyzer_status() -> None:
    result = _result()
    result.applicable_normative_refs = []

    analysis = build_integral_legal_analysis(result)

    assert (
        analysis.readiness.evidentiary_sufficiency
        == EvidentiarySufficiency.INSUFFICIENT
    )
    assert analysis.status == IntegralLegalAnalysisStatus.INSUFFICIENT_EVIDENCE


def test_readiness_does_not_mutate_or_invent_legal_conclusion() -> None:
    result = _result()
    before = result.model_copy(deep=True)

    readiness = evaluate_integral_legal_readiness(result)

    assert readiness.can_close_automatically is True
    assert result == before
