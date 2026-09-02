from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.integral_legal_evidence import IntegralLegalEvidenceMap
from app.domain.integral_legal_readiness import LegalAnalysisReadiness
from app.domain.isr import ISRCalculationResult
from app.domain.query import ExtractedFact, MissingField, QueryIntent
from app.domain.rules import RuleConclusion


class IntegralLegalAnalysisStatus(StrEnum):
    """Estado operativo del análisis jurídico integral."""

    READY = "ready"
    NEEDS_CLARIFICATION = "needs_clarification"
    REVIEW_REQUIRED = "review_required"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class IntegralLegalIssue(BaseModel):
    """Cuestión jurídica identificada sin reinterpretar la consulta."""

    primary_intent: QueryIntent
    secondary_intents: list[QueryIntent] = Field(default_factory=list, max_length=8)


class IntegralLegalAnalysis(BaseModel):
    """Analyzer 1.0: proyección jurídica determinista y auditable."""

    schema_version: str = "1.0"
    issue: IntegralLegalIssue
    facts: list[ExtractedFact] = Field(default_factory=list, max_length=40)
    missing_fields: list[MissingField] = Field(default_factory=list, max_length=20)
    ambiguities: list[str] = Field(default_factory=list, max_length=20)
    applicable_normative_refs: list[str] = Field(default_factory=list, max_length=100)
    rule_conclusions: list[RuleConclusion] = Field(default_factory=list, max_length=100)
    calculation: ISRCalculationResult | None = None
    canonical_conclusion: str | None = Field(default=None, max_length=4000)
    controlling_source: str | None = Field(default=None, max_length=100)
    analysis_priority: list[str] = Field(default_factory=list, max_length=100)
    evidence_map: IntegralLegalEvidenceMap
    readiness: LegalAnalysisReadiness
    requires_human_review: bool = False
    status: IntegralLegalAnalysisStatus
