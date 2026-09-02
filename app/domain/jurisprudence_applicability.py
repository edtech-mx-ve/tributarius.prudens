from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.jurisprudence import JurisprudenceStatus, NormRelationType


class SessionJurisprudenceApplicabilityAssessment(BaseModel):
    """Evaluación conservadora de aplicabilidad para jurisprudencia temporal."""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=3, max_length=200)
    page_number: int = Field(ge=1)
    applicable_candidate: bool
    relevant_to_problem: bool
    relevant_to_norm: bool
    shared_normative_refs: list[str] = Field(default_factory=list, max_length=100)
    criterion_status: JurisprudenceStatus
    relation_type: NormRelationType
    requires_human_review: bool
    reasons: list[str] = Field(default_factory=list, max_length=20)
