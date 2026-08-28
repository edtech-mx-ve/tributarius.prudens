from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class JurisprudenceCriterionType(StrEnum):
    JURISPRUDENCE = "jurisprudence"
    ISOLATED_THESIS = "isolated_thesis"
    PRECEDENT = "precedent"
    UNKNOWN = "unknown"


class JurisprudenceStatus(StrEnum):
    CURRENT = "current"
    HISTORICAL = "historical"
    SUPERSEDED = "superseded"
    INVALIDATED = "invalidated"
    UNKNOWN = "unknown"


class NormRelationType(StrEnum):
    INTERPRETS = "interprets"
    COMPLEMENTS = "complements"
    DISTINGUISHES = "distinguishes"
    CONFLICTS = "conflicts"
    CITES = "cites"
    UNKNOWN = "unknown"


class JurisprudenceActivationReason(StrEnum):
    EXPLICIT_REQUEST = "explicit_request"
    INTERPRETATION_NEEDED = "interpretation_needed"
    AUTHORITY_ACT = "authority_act"
    DEFENSE_ANALYSIS = "defense_analysis"
    AMBIGUITY = "ambiguity"
    NOT_NEEDED = "not_needed"


class JurisprudenceMetadata(BaseModel):
    """Metadatos operativos; no sustituyen la ficha oficial de la fuente."""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=3, max_length=200)
    identifier: str = Field(min_length=1, max_length=300)
    title: str = Field(min_length=1, max_length=1000)
    court_or_body: str = Field(min_length=1, max_length=500)
    criterion_type: JurisprudenceCriterionType
    publication_date: date
    status: JurisprudenceStatus
    matter: str = Field(min_length=1, max_length=300)
    source_reference: str = Field(min_length=1, max_length=1000)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    verified: bool
    related_normative_refs: list[str] = Field(default_factory=list, max_length=100)
    relation_type: NormRelationType = NormRelationType.UNKNOWN
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("related_normative_refs")
    @classmethod
    def normalize_refs(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value or len(value) > 300 for value in cleaned):
            raise ValueError("Referencia normativa inválida.")
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("Las referencias normativas no pueden repetirse.")
        return cleaned

    @model_validator(mode="after")
    def validate_relation(self) -> JurisprudenceMetadata:
        if (
            self.relation_type != NormRelationType.UNKNOWN
            and not self.related_normative_refs
        ):
            raise ValueError(
                "Una relación jurisprudencial explícita requiere referencia normativa."
            )
        return self


class JurisprudenceActivationDecision(BaseModel):
    activated: bool
    reason: JurisprudenceActivationReason
    requires_human_review: bool = False
    detail: str = Field(min_length=1, max_length=1000)


class JurisprudenceCandidateAssessment(BaseModel):
    document_id: str
    identifier: str
    eligible: bool
    relevant_to_norm: bool
    relation_type: NormRelationType
    requires_human_review: bool
    reasons: list[str] = Field(default_factory=list, max_length=20)


class JurisprudenceHit(BaseModel):
    rank: int = Field(ge=1)
    score: float
    chunk_id: str
    text: str
    metadata: JurisprudenceMetadata
    assessment: JurisprudenceCandidateAssessment


class JurisprudenceRetrievalResult(BaseModel):
    activated: bool
    activation: JurisprudenceActivationDecision
    candidate_count: int = Field(ge=0)
    returned_count: int = Field(ge=0)
    hits: list[JurisprudenceHit] = Field(default_factory=list)
    requires_human_review: bool = False
