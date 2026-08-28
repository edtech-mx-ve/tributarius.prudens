from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class SourceType(StrEnum):
    PRODECON = "prodecon"
    UNAM = "unam"
    NORMATIVA = "normativa"
    JURISPRUDENCIA = "jurisprudencia"


class ExtractionStats(BaseModel):
    page_count: int = Field(ge=1)
    extracted_characters: int = Field(ge=0)
    empty_pages: int = Field(ge=0)
    heading_count: int = Field(ge=0)


class DocumentMetadata(BaseModel):
    document_id: str
    source_type: SourceType
    original_filename: str
    source_path: str
    normalized_path: str
    sha256: str = Field(min_length=64, max_length=64)
    processed_at_utc: str
    extractor: str
    extractor_version: str
    stats: ExtractionStats
    warnings: list[str] = Field(default_factory=list)


class ProcessedDocument(BaseModel):
    metadata: DocumentMetadata
    markdown: str
