from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class KnowledgeLayer(StrEnum):
    UNAM = "unam"
    NORMATIVA = "normativa"


class FiscalSourceRole(StrEnum):
    DOCTRINA = "doctrina"
    CONSTITUCIONAL = "constitucional"
    LEY = "ley"
    REGLAMENTO = "reglamento"
    NORMA_ANUAL = "norma_anual"
    REGLA_ADMINISTRATIVA = "regla_administrativa"
    DEFENSA = "defensa"


class ChunkingProfile(StrEnum):
    ACADEMIC_CHAPTER = "academic_chapter"
    LEGAL_ARTICLE = "legal_article"
    ADMINISTRATIVE_RULE = "administrative_rule"


class FiscalDocumentSpec(BaseModel):
    """Especificación controlada de un documento del corpus fiscal local."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    canonical_id: str = Field(pattern=r"^[a-z0-9_]+$", min_length=2, max_length=80)
    filename: str = Field(min_length=5, max_length=180)
    title: str = Field(min_length=3, max_length=300)
    authority: str = Field(min_length=2, max_length=220)
    layer: KnowledgeLayer
    source_role: FiscalSourceRole
    document_type: str = Field(min_length=2, max_length=120)
    matter: list[str] = Field(min_length=1)
    jurisdiction: str = Field(default="México", min_length=2, max_length=100)
    publication_date: date | None = None
    last_reform_date: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    fiscal_year: int | None = Field(default=None, ge=1900, le=2100)
    chunking_profile: ChunkingProfile
    validity_note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_spec(self) -> FiscalDocumentSpec:
        if self.filename != self.filename.strip():
            raise ValueError("filename no puede tener espacios extremos")
        if "/" in self.filename or "\\" in self.filename:
            raise ValueError("filename debe ser un nombre de archivo, no una ruta")
        if not self.filename.lower().endswith(".pdf"):
            raise ValueError("filename debe terminar en .pdf")
        if len(set(self.matter)) != len(self.matter):
            raise ValueError("matter contiene valores duplicados")
        if (
            self.effective_from is not None
            and self.effective_to is not None
            and self.effective_to < self.effective_from
        ):
            raise ValueError("effective_to no puede ser anterior a effective_from")
        return self


class FiscalDocumentResult(BaseModel):
    canonical_id: str
    filename: str
    document_id: str
    source_sha256: str = Field(min_length=64, max_length=64)
    layer: KnowledgeLayer
    source_role: FiscalSourceRole
    normalized_path: str
    metadata_path: str
    legal_metadata_path: str
    page_count: int = Field(ge=1)
    extracted_characters: int = Field(ge=0)
    empty_pages: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class FiscalCorpusManifest(BaseModel):
    schema_version: str = "1.0"
    document_count: int = Field(ge=1)
    documents: list[FiscalDocumentResult]
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_manifest(self) -> FiscalCorpusManifest:
        if self.document_count != len(self.documents):
            raise ValueError("document_count no coincide con documents")
        ids = [item.canonical_id for item in self.documents]
        if len(ids) != len(set(ids)):
            raise ValueError("canonical_id duplicados en el manifiesto")
        return self
