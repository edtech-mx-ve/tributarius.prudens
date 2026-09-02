from __future__ import annotations

from app.domain.integral_legal_analysis import IntegralLegalAnalysisStatus
from app.domain.orchestration import HybridOrchestrationResult
from app.services.integral_legal_analyzer import build_integral_legal_analysis
from tests.test_block12_4_hypothesis_verification import _orchestrator, _request


def _result() -> HybridOrchestrationResult:
    return _orchestrator(None).run(_request())


def test_analyzer_1_0_projects_existing_legal_result_without_recalculation() -> None:
    result = _result()
    analysis = build_integral_legal_analysis(result)

    assert analysis.issue.primary_intent == result.analysis.primary_intent
    assert analysis.issue.secondary_intents == result.analysis.secondary_intents
    assert analysis.facts == result.analysis.facts
    assert analysis.applicable_normative_refs == result.applicable_normative_refs
    assert analysis.rule_conclusions == result.rule_result.matched_rules
    assert analysis.calculation == result.isr_result
    assert analysis.requires_human_review == result.requires_human_review


def test_analyzer_1_0_uses_existing_canonical_conclusion_and_controller() -> None:
    result = _result()
    analysis = build_integral_legal_analysis(result)

    if result.heuristic_evaluation is not None:
        assert (
            analysis.canonical_conclusion
            == result.heuristic_evaluation.canonical_conclusion
        )
        assert (
            analysis.controlling_source
            == result.heuristic_evaluation.controlling_source
        )
    elif result.hybrid_coordination is not None:
        assert analysis.canonical_conclusion == result.hybrid_coordination.conclusion
        assert (
            analysis.controlling_source
            == result.hybrid_coordination.controlling_source
        )
    else:
        assert analysis.canonical_conclusion == result.rule_result.matched_rules[0].conclusion
        assert analysis.controlling_source == "rbs"


def test_analyzer_1_0_preserves_heuristic_analysis_priority() -> None:
    result = _result()
    analysis = build_integral_legal_analysis(result)

    expected = (
        list(result.heuristic_evaluation.analysis_priority)
        if result.heuristic_evaluation is not None
        else []
    )
    assert analysis.analysis_priority == expected


def test_analyzer_1_0_ready_when_deterministic_support_is_available() -> None:
    result = _result()
    analysis = build_integral_legal_analysis(result)

    assert result.applicable_normative_refs or result.rule_result.matched_rules
    assert analysis.status == IntegralLegalAnalysisStatus.READY


def test_analyzer_1_0_requires_clarification_before_declaring_ready() -> None:
    result = _result()
    result.analysis.requires_clarification = True

    analysis = build_integral_legal_analysis(result)

    assert analysis.status == IntegralLegalAnalysisStatus.NEEDS_CLARIFICATION


def test_analyzer_1_0_human_review_has_status_precedence() -> None:
    result = _result()
    result.analysis.requires_clarification = True
    result.requires_human_review = True

    analysis = build_integral_legal_analysis(result)

    assert analysis.requires_human_review is True
    assert analysis.status == IntegralLegalAnalysisStatus.REVIEW_REQUIRED


def test_analyzer_1_0_detects_insufficient_deterministic_evidence() -> None:
    result = _result()
    result.applicable_normative_refs = []
    result.rule_result.matched_rules = []
    result.isr_result = None
    result.hybrid_coordination = None
    result.heuristic_evaluation = None

    analysis = build_integral_legal_analysis(result)

    assert analysis.canonical_conclusion is None
    assert analysis.controlling_source is None
    assert analysis.status == IntegralLegalAnalysisStatus.INSUFFICIENT_EVIDENCE


def test_analyzer_1_0_returns_defensive_copies() -> None:
    result = _result()
    analysis = build_integral_legal_analysis(result)

    if analysis.facts:
        analysis.facts[0].value = "alterado"
        assert analysis.facts != result.analysis.facts

    analysis.applicable_normative_refs.append("REF-NO-PERSISTENTE")
    assert analysis.applicable_normative_refs != result.applicable_normative_refs
