from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class CaseStatus(StrEnum):
    ACTIVE = "active"
    HISTORICAL = "historical"
    SUPERSEDED = "superseded"
    INVALIDATED = "invalidated"


class CaseField(StrEnum):
    TAXPAYER_TYPE = "taxpayer_type"
    ACTIVITY = "activity"
    TAX = "tax"
    PROBLEM_TYPE = "problem_type"
    AUTHORITY_ACT = "authority_act"
    PROCEDURAL_STAGE = "procedural_stage"
    FISCAL_YEAR = "fiscal_year"


class CBRCase(BaseModel):
    case_id: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]{2,99}$")
    status: CaseStatus
    taxpayer_type: str = Field(min_length=1, max_length=100)
    activity: str = Field(min_length=1, max_length=200)
    tax: str = Field(min_length=1, max_length=100)
    problem_type: str = Field(min_length=1, max_length=200)
    authority_act: str | None = Field(default=None, max_length=200)
    procedural_stage: str | None = Field(default=None, max_length=200)
    fiscal_year: int = Field(ge=1900, le=2200)
    resolution_summary: str = Field(min_length=1, max_length=2000)
    normative_refs: list[str] = Field(default_factory=list, max_length=100)
    source_refs: list[str] = Field(min_length=1, max_length=100)
    anonymized: bool = True
    validated: bool = True

    @model_validator(mode="after")
    def validate_case_safety(self) -> CBRCase:
        if not self.anonymized:
            raise ValueError("Los casos CBR deben estar anonimizados.")
        if not self.validated:
            raise ValueError("Los casos CBR deben estar validados.")
        return self


class CBRQuery(BaseModel):
    taxpayer_type: str = Field(min_length=1, max_length=100)
    activity: str = Field(min_length=1, max_length=200)
    tax: str = Field(min_length=1, max_length=100)
    problem_type: str = Field(min_length=1, max_length=200)
    authority_act: str | None = Field(default=None, max_length=200)
    procedural_stage: str | None = Field(default=None, max_length=200)
    fiscal_year: int = Field(ge=1900, le=2200)
    top_k: int = Field(default=5, ge=1, le=20)


class FieldSimilarity(BaseModel):
    field: CaseField
    score: float = Field(ge=0, le=1)
    weight: float = Field(ge=0, le=1)
    query_value: str
    case_value: str


class CBRMatch(BaseModel):
    rank: int = Field(ge=1)
    case_id: str
    status: CaseStatus
    similarity: float = Field(ge=0, le=1)
    resolution_summary: str
    normative_refs: list[str]
    source_refs: list[str]
    field_scores: list[FieldSimilarity]
    explanation: str
    requires_human_review: bool


class CBRRetrievalResult(BaseModel):
    query: CBRQuery
    candidate_count: int = Field(ge=0)
    returned_count: int = Field(ge=0)
    matches: list[CBRMatch]


class RetentionStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class CBRRetentionCandidate(BaseModel):
    candidate_id: str = Field(pattern=r"^CBRCAND-[A-Z0-9_-]{4,90}$")
    proposed_case: CBRCase
    utility_reason: str = Field(min_length=1, max_length=1000)
    status: RetentionStatus = RetentionStatus.PENDING_REVIEW

    @model_validator(mode="after")
    def prevent_auto_activation(self) -> CBRRetentionCandidate:
        if (
            self.status == RetentionStatus.APPROVED
            and self.proposed_case.status == CaseStatus.ACTIVE
        ):
            raise ValueError(
                "La aprobación/activación requiere el flujo de revisión persistente."
            )
        return self


class CBRReuseDecision(StrEnum):
    ELIGIBLE = "eligible"
    REVIEW_REQUIRED = "review_required"
    REJECTED = "rejected"


class CBRReuseAssessment(BaseModel):
    case_id: str
    decision: CBRReuseDecision
    shared_normative_refs: list[str]
    reason: str
    requires_human_review: bool


class CBRRevision(BaseModel):
    source_case_id: str
    revised_resolution_summary: str = Field(min_length=1, max_length=2000)
    reviewer_confirmed: bool


class AnonymizationResult(BaseModel):
    text: str
    redaction_count: int = Field(ge=0)
    detected_types: list[str]
    requires_human_review: bool = True
