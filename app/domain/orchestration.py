from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from app.domain.cbr import CBRQuery, CBRRetrievalResult, CBRReuseAssessment
from app.domain.isr import ISRCalculationInput, ISRCalculationResult
from app.domain.jurisprudence import JurisprudenceRetrievalResult
from app.domain.normative import NormativeApplicabilityResult
from app.domain.query import QueryAnalysis
from app.domain.rules import RuleEvaluationResult
from llm.models import RAGExplanation
from rag.retrieval.models import RetrievalResult


class OrchestrationStage(StrEnum):
    QUERY_ANALYSIS = "query_analysis"
    RETRIEVAL = "retrieval"
    NORMATIVE = "normative"
    JURISPRUDENCE = "jurisprudence"
    RULES = "rules"
    ISR = "isr"
    CBR = "cbr"
    EXPLANATION = "explanation"


class StageStatus(StrEnum):
    COMPLETED = "completed"
    SKIPPED = "skipped"
    DEGRADED = "degraded"


class StageTrace(BaseModel):
    stage: OrchestrationStage
    status: StageStatus
    detail: str = Field(min_length=1, max_length=1000)


class NormativeCandidate(BaseModel):
    ref: str = Field(min_length=1, max_length=300)
    legal_unit_id: int = Field(gt=0)
    version_label: str = Field(min_length=1, max_length=100)
    effective_from: date | None = None
    effective_to: date | None = None
    fiscal_year: int | None = Field(default=None, ge=1900, le=2200)

    @model_validator(mode="after")
    def validate_interval(self) -> NormativeCandidate:
        if (
            self.effective_from is not None
            and self.effective_to is not None
            and self.effective_to < self.effective_from
        ):
            raise ValueError("effective_to no puede ser anterior a effective_from.")
        return self


class HybridOrchestrationRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    query_date: date
    query_fiscal_year: int | None = Field(default=None, ge=1900, le=2200)
    top_k: int = Field(default=5, ge=1, le=20)
    normative_candidates: list[NormativeCandidate] = Field(
        default_factory=list,
        max_length=100,
    )
    isr_input: ISRCalculationInput | None = None
    cbr_query: CBRQuery | None = None


class HybridOrchestrationResult(BaseModel):
    analysis: QueryAnalysis
    retrieval: RetrievalResult
    normative_results: list[NormativeApplicabilityResult]
    applicable_normative_refs: list[str]
    jurisprudence_result: JurisprudenceRetrievalResult | None = None
    rule_result: RuleEvaluationResult
    isr_result: ISRCalculationResult | None = None
    cbr_result: CBRRetrievalResult | None = None
    cbr_reuse_assessments: list[CBRReuseAssessment] = Field(default_factory=list)
    explanation: RAGExplanation | None = None
    traces: list[StageTrace]
    requires_human_review: bool
