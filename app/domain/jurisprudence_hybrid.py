from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.jurisprudence_applicability import (
    SessionJurisprudenceApplicabilityAssessment,
)
from app.domain.jurisprudence_relations import JurisprudenceConflictAnalysis
from app.domain.jurisprudence_session_retrieval import (
    SessionJurisprudenceRetrievalResult,
)


class SessionJurisprudenceHybridResult(BaseModel):
    """Resultado jurisprudencial temporal listo para el orquestador híbrido."""

    model_config = ConfigDict(extra="forbid")

    retrieval: SessionJurisprudenceRetrievalResult
    applicability: list[SessionJurisprudenceApplicabilityAssessment] = Field(
        default_factory=list
    )
    relations: JurisprudenceConflictAnalysis
    evidence: list[str] = Field(default_factory=list)
    requires_human_review: bool
