from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.cbr import CaseStatus, CBRQuery, CBRReuseDecision, FieldSimilarity


class CBRCaseReasoningTrace(BaseModel):
    rank: int = Field(ge=1)
    case_id: str = Field(min_length=1, max_length=100)
    status: CaseStatus
    similarity: float = Field(ge=0, le=1)
    field_scores: list[FieldSimilarity]
    normative_refs: list[str]
    source_refs: list[str]
    reuse_decision: CBRReuseDecision
    reuse_reason: str = Field(min_length=1, max_length=1000)
    shared_normative_refs: list[str]
    requires_human_review: bool


class CBRReasoningTrace(BaseModel):
    query: CBRQuery
    candidate_count: int = Field(ge=0)
    returned_count: int = Field(ge=0)
    cases: list[CBRCaseReasoningTrace]
    requires_human_review: bool
