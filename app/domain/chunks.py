from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from app.domain.documents import SourceType


class LegalChunkType(StrEnum):
    DOCUMENT = "document"
    TITLE = "title"
    CHAPTER = "chapter"
    SECTION = "section"
    ARTICLE = "article"
    FRACTION = "fraction"
    SUBSECTION = "subsection"
    PARAGRAPH = "paragraph"


class LegalHierarchy(BaseModel):
    title: str | None = None
    chapter: str | None = None
    section: str | None = None
    article: str | None = None
    fraction: str | None = None
    subsection: str | None = None


class ChunkMetadata(BaseModel):
    document_id: str = Field(min_length=3, max_length=200)
    source_type: SourceType
    source_filename: str = Field(min_length=1, max_length=300)
    chunk_index: int = Field(ge=0)
    chunk_type: LegalChunkType
    legal_identifier: str | None = Field(default=None, max_length=300)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    hierarchy: LegalHierarchy
    source_sha256: str = Field(min_length=64, max_length=64)
    fiscal_year: int | None = Field(default=None, ge=1900, le=2200)
    version_label: str | None = Field(default=None, max_length=100)
    canonical_id: str | None = Field(default=None, max_length=80)
    source_role: str | None = Field(default=None, max_length=80)
    document_type: str | None = Field(default=None, max_length=120)
    title: str | None = Field(default=None, max_length=500)
    source_unit_type: str | None = Field(default=None, max_length=80)
    source_unit_label: str | None = Field(default=None, max_length=300)
    matter: list[str] = Field(default_factory=list)
    jurisdiction: str | None = Field(default=None, max_length=100)
    publication_date: str | None = Field(default=None, max_length=40)
    last_reform_date: str | None = Field(default=None, max_length=40)
    effective_from: str | None = Field(default=None, max_length=40)
    effective_to: str | None = Field(default=None, max_length=40)
    validity_status: str | None = Field(default=None, max_length=40)
    validity_scope: str | None = Field(default=None, max_length=40)
    validity_basis: str | None = Field(default=None, max_length=80)
    validity_verified_at: str | None = Field(default=None, max_length=40)
    official_source: str | None = Field(default=None, max_length=1000)
    text_sha256: str | None = Field(default=None, min_length=64, max_length=64)

    # Sprint 19F: identidad canónica y trazabilidad del subchunk de recuperación.
    parent_chunk_id: str | None = Field(default=None, min_length=8, max_length=300)
    retrieval_subchunk_index: int | None = Field(default=None, ge=0)
    retrieval_subchunk_count: int | None = Field(default=None, ge=1)
    retrieval_strategy: str | None = Field(default=None, max_length=80)
    retrieval_text_sha256: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )

    @model_validator(mode="after")
    def validate_page_range(self) -> ChunkMetadata:
        if (
            self.page_start is not None
            and self.page_end is not None
            and self.page_end < self.page_start
        ):
            raise ValueError("page_end no puede ser anterior a page_start")
        return self

    @model_validator(mode="after")
    def validate_retrieval_trace(self) -> ChunkMetadata:
        fields = (
            self.retrieval_subchunk_index,
            self.retrieval_subchunk_count,
            self.retrieval_strategy,
            self.retrieval_text_sha256,
        )
        if self.parent_chunk_id is None and any(value is not None for value in fields):
            raise ValueError(
                "Los metadatos de recuperación requieren parent_chunk_id."
            )
        if self.parent_chunk_id is not None:
            if self.retrieval_subchunk_index is None:
                raise ValueError("Falta retrieval_subchunk_index.")
            if self.retrieval_subchunk_count is None:
                raise ValueError("Falta retrieval_subchunk_count.")
            if self.retrieval_subchunk_index >= self.retrieval_subchunk_count:
                raise ValueError(
                    "retrieval_subchunk_index debe ser menor que "
                    "retrieval_subchunk_count."
                )
        return self


class LegalChunk(BaseModel):
    chunk_id: str = Field(min_length=8, max_length=300)
    text: str = Field(min_length=1)
    metadata: ChunkMetadata


class ChunkingReport(BaseModel):
    document_id: str
    chunk_count: int = Field(ge=0)
    by_type: dict[str, int] = Field(default_factory=dict)
    pages_seen: list[int] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
