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
    title: str | None = Field(default=None, max_length=1000)
    court_or_body: str | None = Field(default=None, max_length=500)
    criterion_type: JurisprudenceCriterionType = JurisprudenceCriterionType.UNKNOWN
    publication_date_text: str | None = Field(default=None, max_length=300)
    status: JurisprudenceStatus = JurisprudenceStatus.UNKNOWN
    matter: str | None = Field(default=None, max_length=300)
    related_normative_refs: list[str] = Field(default_factory=list, max_length=100)
    relation_type: NormRelationType = NormRelationType.UNKNOWN
    source_pages: list[int] = Field(default_factory=list)
    requires_human_review: bool = True
    warnings: list[str] = Field(default_factory=list)
