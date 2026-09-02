from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class JurisprudencePage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: int = Field(ge=1)
    text: str
    has_extractable_text: bool


class JurisprudenceDocumentRepresentation(BaseModel):
    """Representación documental previa a identificar criterios jurídicos."""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=3, max_length=200)
    original_filename: str = Field(min_length=1, max_length=500)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    page_count: int = Field(ge=1)
    extracted_characters: int = Field(ge=1)
    pages: list[JurisprudencePage] = Field(min_length=1)
    full_text: str = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)
