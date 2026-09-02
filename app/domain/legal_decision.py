from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.integral_legal_analysis import IntegralLegalIssue
from app.domain.integral_legal_evidence import IntegralLegalEvidenceMap
from app.domain.integral_legal_readiness import LegalAnalysisReadiness
from app.domain.isr import ISRCalculationResult
from app.domain.legal_consequences import LegalConsequences
from app.domain.legal_fact_assessment import LegalFactAssessment
from app.domain.legal_reasoning_chain import LegalReasoningChain
from app.domain.query import ExtractedFact, MissingField
from app.domain.rules import RuleConclusion


class LegalDecisionStatus(StrEnum):
    """Estado de la determinación jurídica formalizada."""

    DETERMINED = "determined"
    CONDITIONALLY_DETERMINED = "conditionally_determined"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    HUMAN_REVIEW_REQUIRED = "human_review_required"


class LegalDecision(BaseModel):
    """Legal Decision 1.0: determinación derivada exclusivamente de Analyzer 1.0."""

    schema_version: str = "1.0"
    source_analysis_schema_version: str = Field(max_length=20)
    issue: IntegralLegalIssue
    facts: list[ExtractedFact] = Field(default_factory=list, max_length=40)
    fact_assessments: list[LegalFactAssessment] = Field(
        default_factory=list,
        max_length=60,
    )
    reasoning_chain: LegalReasoningChain = Field(default_factory=LegalReasoningChain)
    consequences: LegalConsequences = Field(default_factory=LegalConsequences)
    missing_fields: list[MissingField] = Field(default_factory=list, max_length=20)
    ambiguities: list[str] = Field(default_factory=list, max_length=20)
    applicable_normative_refs: list[str] = Field(default_factory=list, max_length=100)
    rule_conclusions: list[RuleConclusion] = Field(default_factory=list, max_length=100)
    calculation: ISRCalculationResult | None = None
    conclusion: str | None = Field(default=None, max_length=4000)
    controlling_source: str | None = Field(default=None, max_length=100)
    analysis_priority: list[str] = Field(default_factory=list, max_length=100)
    evidence_map: IntegralLegalEvidenceMap
    readiness: LegalAnalysisReadiness
    requires_human_review: bool = False
    status: LegalDecisionStatus
