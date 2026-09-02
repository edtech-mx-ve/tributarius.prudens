from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.domain.jurisprudence import NormRelationType


class JurisprudenceComparisonType(StrEnum):
    CONCORDANT = "concordant"
    DISTINGUISHABLE = "distinguishable"
    CONTRADICTORY = "contradictory"
    UNDETERMINED = "undetermined"


class JurisprudenceRelationAssessment(BaseModel):
    """Relación controlada entre un criterio candidato y el problema jurídico."""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=3, max_length=200)
    relation: JurisprudenceComparisonType
    normative_relation: NormRelationType
    shared_normative_refs: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    requires_human_review: bool = True


class JurisprudenceConflictAnalysis(BaseModel):
    """Resumen de concordancias, distinciones y contradicciones detectadas."""

    model_config = ConfigDict(extra="forbid")

    assessments: list[JurisprudenceRelationAssessment] = Field(default_factory=list)
    concordant_count: int = Field(ge=0)
    distinguishable_count: int = Field(ge=0)
    contradictory_count: int = Field(ge=0)
    undetermined_count: int = Field(ge=0)
    has_conflict: bool
    requires_human_review: bool
