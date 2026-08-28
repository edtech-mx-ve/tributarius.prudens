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

    @model_validator(mode="after")
    def validate_page_range(self) -> ChunkMetadata:
        if (
            self.page_start is not None
            and self.page_end is not None
            and self.page_end < self.page_start
        ):
            raise ValueError("page_end no puede ser anterior a page_start")
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
