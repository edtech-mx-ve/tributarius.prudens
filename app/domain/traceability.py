from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class TraceEventStatus(StrEnum):
    COMPLETED = "completed"
    SKIPPED = "skipped"
    DEGRADED = "degraded"
    REVIEW_REQUIRED = "review_required"


class EvidenceKind(StrEnum):
    DOCUMENT = "document"
    NORMATIVE = "normative"
    RULE = "rule"
    CALCULATION = "calculation"
    CBR_CASE = "cbr_case"
    JURISPRUDENCE = "jurisprudence"
    LLM_EXPLANATION = "llm_explanation"
    HYBRID_COORDINATION = "hybrid_coordination"


class TraceEvent(BaseModel):
    sequence: int = Field(ge=1)
    stage: str = Field(min_length=1, max_length=100)
    status: TraceEventStatus
    summary: str = Field(min_length=1, max_length=1000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=200)
    requires_human_review: bool = False


class EvidenceReference(BaseModel):
    ref_id: str = Field(min_length=1, max_length=300)
    kind: EvidenceKind
    source_type: str | None = Field(default=None, max_length=100)
    source_reference: str | None = Field(default=None, max_length=1000)
    version: str | None = Field(default=None, max_length=200)
    fiscal_year: int | None = Field(default=None, ge=1900, le=2200)
    score: float | None = Field(default=None, ge=-1, le=1)


class UncertaintyItem(BaseModel):
    code: str = Field(pattern=r"^[A-Z0-9_]{3,100}$")
    message: str = Field(min_length=1, max_length=1000)
    stage: str = Field(min_length=1, max_length=100)
    requires_human_review: bool = False


class HybridDecisionTrace(BaseModel):
    """Traza estructurada de la decisión híbrida RBS-CBR."""

    relation: str = Field(min_length=1, max_length=100)
    conclusion: str | None = Field(default=None, max_length=4000)
    controlling_source: str | None = Field(default=None, max_length=100)
    shared_legal_basis: list[str] = Field(default_factory=list, max_length=200)
    reasons: list[str] = Field(default_factory=list, max_length=100)
    factors: dict[str, Any] = Field(default_factory=dict)
    rbs_trace: list[str] = Field(default_factory=list, max_length=200)
    cbr_trace: list[str] = Field(default_factory=list, max_length=200)
    requires_human_review: bool = False


class TraceabilityRecord(BaseModel):
    schema_version: str = "1.0"
    execution_id: str = Field(pattern=r"^TP-[A-F0-9]{32}$")
    folio: str = Field(pattern=r"^TP-\d{8}-[A-F0-9]{12}$")
    created_at_utc: datetime
    query_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    primary_intent: str
    query_fiscal_year: int | None = Field(default=None, ge=1900, le=2200)
    events: list[TraceEvent] = Field(min_length=1)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    jurisprudential_sources: list[EvidenceReference] = Field(default_factory=list)
    uncertainties: list[UncertaintyItem] = Field(default_factory=list)
    hybrid_decision: HybridDecisionTrace | None = None
    requires_human_review: bool
    canonical_result_sha256: str | None = Field(
        default=None,
        pattern=r"^[a-f0-9]{64}$",
    )


class CanonicalExecutionResult(BaseModel):
    schema_version: str = "1.0"
    execution_id: str
    folio: str
    created_at_utc: datetime
    query_analysis: dict[str, Any]
    retrieval: dict[str, Any]
    normative: dict[str, Any]
    rules: dict[str, Any]
    jurisprudence: dict[str, Any] | None = None
    session_jurisprudence: dict[str, Any] | None = None
    calculations: dict[str, Any]
    cbr: dict[str, Any]
    hybrid_coordination: dict[str, Any] | None = None
    explanation: dict[str, Any] | None
    llm_trace: dict[str, Any] | None = None
    uncertainty: dict[str, Any]
    traceability: TraceabilityRecord
