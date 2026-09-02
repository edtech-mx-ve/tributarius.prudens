from __future__ import annotations

from app.domain.integral_legal_analysis import (
    IntegralLegalAnalysis,
    IntegralLegalAnalysisStatus,
    IntegralLegalIssue,
)
from app.domain.integral_legal_readiness import EvidentiarySufficiency
from app.domain.orchestration import HybridOrchestrationResult
from app.services.integral_legal_evidence import build_integral_legal_evidence_map
from app.services.integral_legal_readiness import evaluate_integral_legal_readiness


def _canonical_conclusion(result: HybridOrchestrationResult) -> str | None:
    heuristics = result.heuristic_evaluation
    if heuristics is not None and heuristics.canonical_conclusion:
        return heuristics.canonical_conclusion

    coordination = result.hybrid_coordination
    if coordination is not None and coordination.conclusion:
        return coordination.conclusion

    if result.rule_result.matched_rules:
        return result.rule_result.matched_rules[0].conclusion

    return None


def _controlling_source(result: HybridOrchestrationResult) -> str | None:
    heuristics = result.heuristic_evaluation
    if heuristics is not None and heuristics.controlling_source:
        return heuristics.controlling_source

    coordination = result.hybrid_coordination
    if coordination is not None and coordination.controlling_source:
        return coordination.controlling_source

    if result.rule_result.matched_rules:
        return "rbs"

    return None


def _analysis_priority(result: HybridOrchestrationResult) -> list[str]:
    heuristics = result.heuristic_evaluation
    if heuristics is None:
        return []
    return list(heuristics.analysis_priority)


def _status(
    result: HybridOrchestrationResult,
    sufficiency: EvidentiarySufficiency,
) -> IntegralLegalAnalysisStatus:
    if result.requires_human_review:
        return IntegralLegalAnalysisStatus.REVIEW_REQUIRED

    if result.analysis.requires_clarification:
        return IntegralLegalAnalysisStatus.NEEDS_CLARIFICATION

    if sufficiency == EvidentiarySufficiency.INSUFFICIENT:
        return IntegralLegalAnalysisStatus.INSUFFICIENT_EVIDENCE

    return IntegralLegalAnalysisStatus.READY


def build_integral_legal_analysis(
    result: HybridOrchestrationResult,
) -> IntegralLegalAnalysis:
    """Construye Analyzer 1.0 sin ejecutar ni reinterpretar razonamiento nuevo."""

    readiness = evaluate_integral_legal_readiness(result)
    evidence_map = build_integral_legal_evidence_map(result)

    return IntegralLegalAnalysis(
        issue=IntegralLegalIssue(
            primary_intent=result.analysis.primary_intent,
            secondary_intents=list(result.analysis.secondary_intents),
        ),
        facts=[fact.model_copy(deep=True) for fact in result.analysis.facts],
        missing_fields=[
            field.model_copy(deep=True) for field in result.analysis.missing_fields
        ],
        ambiguities=list(result.analysis.ambiguities),
        applicable_normative_refs=list(result.applicable_normative_refs),
        rule_conclusions=[
            conclusion.model_copy(deep=True)
            for conclusion in result.rule_result.matched_rules
        ],
        calculation=(
            result.isr_result.model_copy(deep=True)
            if result.isr_result is not None
            else None
        ),
        canonical_conclusion=_canonical_conclusion(result),
        controlling_source=_controlling_source(result),
        analysis_priority=_analysis_priority(result),
        evidence_map=evidence_map,
        readiness=readiness,
        requires_human_review=result.requires_human_review,
        status=_status(result, readiness.evidentiary_sufficiency),
    )
