from __future__ import annotations

from app.domain.integral_legal_analysis import (
    IntegralLegalAnalysis,
    IntegralLegalAnalysisStatus,
)
from app.domain.legal_decision import LegalDecision, LegalDecisionStatus
from app.services.legal_consequences import build_legal_consequences
from app.services.legal_fact_assessment import assess_legal_facts
from app.services.legal_reasoning_chain import build_legal_reasoning_chain


def _decision_status(analysis: IntegralLegalAnalysis) -> LegalDecisionStatus:
    """Proyecta el estado de Analyzer 1.0 sin volver a decidir el fondo jurídico."""

    if analysis.requires_human_review:
        return LegalDecisionStatus.HUMAN_REVIEW_REQUIRED

    if (
        analysis.status == IntegralLegalAnalysisStatus.INSUFFICIENT_EVIDENCE
        or analysis.canonical_conclusion is None
    ):
        return LegalDecisionStatus.INSUFFICIENT_EVIDENCE

    if analysis.status == IntegralLegalAnalysisStatus.NEEDS_CLARIFICATION:
        return LegalDecisionStatus.CONDITIONALLY_DETERMINED

    if analysis.status == IntegralLegalAnalysisStatus.REVIEW_REQUIRED:
        return LegalDecisionStatus.HUMAN_REVIEW_REQUIRED

    return LegalDecisionStatus.DETERMINED


def build_legal_decision(analysis: IntegralLegalAnalysis) -> LegalDecision:
    """Formaliza Analyzer 1.0 sin crear una segunda conclusión jurídica."""

    decision = LegalDecision(
        source_analysis_schema_version=analysis.schema_version,
        issue=analysis.issue.model_copy(deep=True),
        facts=[fact.model_copy(deep=True) for fact in analysis.facts],
        fact_assessments=[
            assessment.model_copy(deep=True)
            for assessment in assess_legal_facts(analysis)
        ],
        missing_fields=[
            field.model_copy(deep=True) for field in analysis.missing_fields
        ],
        ambiguities=list(analysis.ambiguities),
        applicable_normative_refs=list(analysis.applicable_normative_refs),
        rule_conclusions=[
            conclusion.model_copy(deep=True)
            for conclusion in analysis.rule_conclusions
        ],
        calculation=(
            analysis.calculation.model_copy(deep=True)
            if analysis.calculation is not None
            else None
        ),
        conclusion=analysis.canonical_conclusion,
        controlling_source=analysis.controlling_source,
        analysis_priority=list(analysis.analysis_priority),
        evidence_map=analysis.evidence_map.model_copy(deep=True),
        jurisprudence_application=(
            analysis.jurisprudence_application.model_copy(deep=True)
            if analysis.jurisprudence_application is not None
            else None
        ),
        readiness=analysis.readiness.model_copy(deep=True),
        requires_human_review=analysis.requires_human_review,
        status=_decision_status(analysis),
    )
    decision.reasoning_chain = build_legal_reasoning_chain(decision)
    decision.consequences = build_legal_consequences(decision)
    return decision
