from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LegalUnitType(StrEnum):
    PRODECON_SECTION = "prodecon_section"
    ACADEMIC_CHAPTER = "academic_chapter"
    ARTICLE = "article"
    ADMINISTRATIVE_RULE = "administrative_rule"
    STRUCTURAL_SECTION = "structural_section"


class LegalChunk(BaseModel):
    """Unidad recuperable del corpus fiscal, con trazabilidad de origen."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    chunk_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.:-]+$", min_length=8, max_length=180)
    canonical_id: str = Field(pattern=r"^[a-z0-9_]+$", min_length=2, max_length=80)
    source_role: str = Field(min_length=2, max_length=80)
    document_type: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=1, max_length=500)
    unit_type: LegalUnitType
    unit_label: str = Field(min_length=1, max_length=300)
    hierarchy: list[str] = Field(default_factory=list)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    fiscal_year: int | None = Field(default=None, ge=1900, le=2100)
    source_sha256: str = Field(min_length=64, max_length=64)
    text_sha256: str = Field(min_length=64, max_length=64)
    text: str = Field(min_length=1)
    matter: list[str] = Field(default_factory=list)
    jurisdiction: str = Field(default="México", min_length=2, max_length=100)
    publication_date: str | None = None
    last_reform_date: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None

    @model_validator(mode="after")
    def validate_pages(self) -> LegalChunk:
        if (
            self.page_start is not None
            and self.page_end is not None
            and self.page_end < self.page_start
        ):
            raise ValueError("page_end no puede ser anterior a page_start")
        return self


class ChunkingDocumentSummary(BaseModel):
    canonical_id: str
    profile: str
    chunks: int = Field(ge=1)
    structured_chunks: int = Field(ge=0)
    fallback_chunks: int = Field(ge=0)
    characters: int = Field(ge=1)


class LegalChunkingManifest(BaseModel):
    schema_version: str = "1.0"
    document_count: int = Field(ge=1)
    chunk_count: int = Field(ge=1)
    chunks_sha256: str = Field(min_length=64, max_length=64)
    documents: list[ChunkingDocumentSummary]
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_counts(self) -> LegalChunkingManifest:
        if self.document_count != len(self.documents):
            raise ValueError("document_count no coincide con documents")
        if self.chunk_count != sum(item.chunks for item in self.documents):
            raise ValueError("chunk_count no coincide con la suma de chunks")
        return self
