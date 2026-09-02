from __future__ import annotations

from app.domain.integral_legal_analysis import IntegralLegalAnalysis, IntegralLegalAnalysisStatus
from app.domain.legal_decision import LegalDecisionStatus
from app.services.integral_legal_analyzer import build_integral_legal_analysis
from app.services.legal_decision import build_legal_decision
from tests.test_block12_4_hypothesis_verification import _orchestrator, _request


def _analysis() -> IntegralLegalAnalysis:
    result = _orchestrator(None).run(_request())
    return build_integral_legal_analysis(result)


def test_legal_decision_1_0_projects_analyzer_without_recalculation() -> None:
    analysis = _analysis()

    decision = build_legal_decision(analysis)

    assert decision.source_analysis_schema_version == analysis.schema_version
    assert decision.issue == analysis.issue
    assert decision.facts == analysis.facts
    assert decision.applicable_normative_refs == analysis.applicable_normative_refs
    assert decision.rule_conclusions == analysis.rule_conclusions
    assert decision.calculation == analysis.calculation
    assert decision.evidence_map == analysis.evidence_map
    assert decision.readiness == analysis.readiness


def test_legal_decision_1_0_preserves_single_canonical_conclusion() -> None:
    analysis = _analysis()

    decision = build_legal_decision(analysis)

    assert decision.conclusion == analysis.canonical_conclusion
    assert decision.controlling_source == analysis.controlling_source


def test_legal_decision_1_0_never_promotes_llama_as_controller() -> None:
    analysis = _analysis()

    decision = build_legal_decision(analysis)

    assert decision.controlling_source != "llama"


def test_legal_decision_1_0_is_determined_when_analyzer_is_ready() -> None:
    analysis = _analysis()
    assert analysis.status == IntegralLegalAnalysisStatus.READY
    assert analysis.canonical_conclusion is not None

    decision = build_legal_decision(analysis)

    assert decision.status == LegalDecisionStatus.DETERMINED


def test_legal_decision_1_0_is_conditional_when_clarification_is_pending() -> None:
    analysis = _analysis()
    analysis.status = IntegralLegalAnalysisStatus.NEEDS_CLARIFICATION
    assert analysis.canonical_conclusion is not None

    decision = build_legal_decision(analysis)

    assert decision.conclusion == analysis.canonical_conclusion
    assert decision.status == LegalDecisionStatus.CONDITIONALLY_DETERMINED


def test_legal_decision_1_0_preserves_human_review_without_downgrade() -> None:
    analysis = _analysis()
    analysis.requires_human_review = True
    analysis.status = IntegralLegalAnalysisStatus.REVIEW_REQUIRED

    decision = build_legal_decision(analysis)

    assert decision.requires_human_review is True
    assert decision.status == LegalDecisionStatus.HUMAN_REVIEW_REQUIRED


def test_legal_decision_1_0_rejects_false_determination_without_conclusion() -> None:
    analysis = _analysis()
    analysis.canonical_conclusion = None
    analysis.status = IntegralLegalAnalysisStatus.INSUFFICIENT_EVIDENCE

    decision = build_legal_decision(analysis)

    assert decision.conclusion is None
    assert decision.status == LegalDecisionStatus.INSUFFICIENT_EVIDENCE


def test_legal_decision_1_0_preserves_analysis_priority_and_uncertainty() -> None:
    analysis = _analysis()

    decision = build_legal_decision(analysis)

    assert decision.analysis_priority == analysis.analysis_priority
    assert decision.missing_fields == analysis.missing_fields
    assert decision.ambiguities == analysis.ambiguities


def test_legal_decision_1_0_returns_defensive_copies() -> None:
    analysis = _analysis()

    decision = build_legal_decision(analysis)

    decision.applicable_normative_refs.append("REF-NO-PERSISTENTE")
    assert decision.applicable_normative_refs != analysis.applicable_normative_refs

    if decision.facts:
        decision.facts[0].value = "alterado"
        assert decision.facts != analysis.facts

    decision.evidence_map.items[0].references.append("EVIDENCIA-NO-PERSISTENTE")
    assert decision.evidence_map != analysis.evidence_map
