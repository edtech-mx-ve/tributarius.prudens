from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.jurisprudence import (
    JurisprudenceCriterionType,
    JurisprudenceStatus,
    NormRelationType,
)


class JurisprudenceExtractedMetadata(BaseModel):
    """Metadatos identificados desde el documento, todavía no verificados."""

    model_config = ConfigDict(extra="forbid")

    identifier: str | None = Field(default=None, max_length=300)
    thesis_number: str | None = Field(default=None, max_length=300)
    title: str | None = Field(default=None, max_length=1000)
    court_or_body: str | None = Field(default=None, max_length=500)
    criterion_type: JurisprudenceCriterionType = JurisprudenceCriterionType.UNKNOWN
    publication_date_text: str | None = Field(default=None, max_length=300)
    publication_source: str | None = Field(default=None, max_length=500)
    epoch: str | None = Field(default=None, max_length=200)
    status: JurisprudenceStatus = JurisprudenceStatus.UNKNOWN
    matter: str | None = Field(default=None, max_length=300)
    binding_force_text: str | None = Field(default=None, max_length=1000)
    binding_effective_date_text: str | None = Field(default=None, max_length=300)
    facts_text: str | None = Field(default=None, max_length=12000)
    legal_criterion_text: str | None = Field(default=None, max_length=12000)
    justification_text: str | None = Field(default=None, max_length=24000)
    criterion_text: str | None = Field(default=None, max_length=12000)
    related_normative_refs: list[str] = Field(default_factory=list, max_length=100)
    relation_type: NormRelationType = NormRelationType.UNKNOWN
    source_pages: list[int] = Field(default_factory=list)
    requires_human_review: bool = True
    warnings: list[str] = Field(default_factory=list)
