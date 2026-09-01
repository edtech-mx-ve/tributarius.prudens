from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from app.domain.cbr import CBRQuery, CBRRetrievalResult, CBRReuseAssessment
from app.domain.documents import SourceType
from app.domain.isr import ISRCalculationInput, ISRCalculationResult
from app.domain.jurisprudence import JurisprudenceRetrievalResult
from app.domain.normative import (
    NormativeApplicabilityResult,
    NormativeValidityBasis,
    NormativeValidityScope,
    NormativeValidityStatus,
)
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


class EvidenceRole(StrEnum):
    ORIENTATIVE = "orientative"
    ACADEMIC_FOUNDATION = "academic_foundation"
    NORMATIVE = "normative"


class EvidenceLayer(BaseModel):
    role: EvidenceRole
    source_type: SourceType
    refs: list[str] = Field(default_factory=list)


class NormativeCandidate(BaseModel):
    ref: str = Field(min_length=1, max_length=300)
    legal_unit_id: int = Field(gt=0)
    version_label: str = Field(min_length=1, max_length=100)
    effective_from: date | None = None
    effective_to: date | None = None
    fiscal_year: int | None = Field(default=None, ge=1900, le=2200)
    validity_status: NormativeValidityStatus = NormativeValidityStatus.UNKNOWN
    validity_scope: NormativeValidityScope = NormativeValidityScope.UNKNOWN
    validity_basis: NormativeValidityBasis = NormativeValidityBasis.UNKNOWN
    validity_verified_at: date | None = None
    official_source: str | None = Field(default=None, max_length=1000)

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
    normative_candidates: list[NormativeCandidate] = Field(default_factory=list, max_length=100)
    isr_input: ISRCalculationInput | None = None
    cbr_query: CBRQuery | None = None


def classify_retrieval_evidence(
    retrieval: RetrievalResult,
) -> tuple[list[str], list[str]]:
    """Separa evidencia orientativa PRODECON y fundamento académico UNAM."""
    prodecon_refs: list[str] = []
    unam_refs: list[str] = []
    for hit in retrieval.hits:
        if hit.metadata.source_type == SourceType.PRODECON:
            prodecon_refs.append(hit.chunk_id)
        elif hit.metadata.source_type == SourceType.UNAM:
            unam_refs.append(hit.chunk_id)
    return prodecon_refs, unam_refs


def build_evidence_layers(
    retrieval: RetrievalResult,
    normative_evidence_refs: list[str],
) -> list[EvidenceLayer]:
    """Expresa la función jurídica de cada capa sin confundir autoridad normativa."""
    prodecon_refs, unam_refs = classify_retrieval_evidence(retrieval)
    return [
        EvidenceLayer(
            role=EvidenceRole.ORIENTATIVE,
            source_type=SourceType.PRODECON,
            refs=prodecon_refs,
        ),
        EvidenceLayer(
            role=EvidenceRole.ACADEMIC_FOUNDATION,
            source_type=SourceType.UNAM,
            refs=unam_refs,
        ),
        EvidenceLayer(
            role=EvidenceRole.NORMATIVE,
            source_type=SourceType.NORMATIVA,
            refs=list(normative_evidence_refs),
        ),
    ]


class HybridOrchestrationResult(BaseModel):
    analysis: QueryAnalysis
    retrieval: RetrievalResult
    prodecon_evidence_refs: list[str] = Field(default_factory=list)
    unam_evidence_refs: list[str] = Field(default_factory=list)
    evidence_layers: list[EvidenceLayer] = Field(default_factory=list)
    normative_candidates: list[NormativeCandidate] = Field(default_factory=list)
    normative_results: list[NormativeApplicabilityResult]
    normative_evidence_refs: list[str] = Field(default_factory=list)
    applicable_normative_refs: list[str]
    jurisprudence_result: JurisprudenceRetrievalResult | None = None
    rule_result: RuleEvaluationResult
    isr_result: ISRCalculationResult | None = None
    cbr_result: CBRRetrievalResult | None = None
    cbr_reuse_assessments: list[CBRReuseAssessment] = Field(default_factory=list)
    explanation: RAGExplanation | None = None
    traces: list[StageTrace]
    requires_human_review: bool

    @model_validator(mode="after")
    def preserve_complementary_evidence(self) -> HybridOrchestrationResult:
        prodecon_refs, unam_refs = classify_retrieval_evidence(self.retrieval)
        self.prodecon_evidence_refs = prodecon_refs
        self.unam_evidence_refs = unam_refs
        self.evidence_layers = build_evidence_layers(
            self.retrieval,
            self.normative_evidence_refs,
        )
        return self
