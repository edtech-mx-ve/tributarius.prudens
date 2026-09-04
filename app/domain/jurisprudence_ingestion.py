from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.chunks import ChunkingReport, LegalChunk
from app.domain.documents import ProcessedDocument, SourceType


class JurisprudenceIngestionStatus(StrEnum):
    READY = "ready"


class JurisprudenceSourceScope(StrEnum):
    SESSION = "session"


class JurisprudenceIngestionReceipt(BaseModel):
    """Contrato E.1 de ingesta; no expresa valoración jurídica del criterio."""

    model_config = ConfigDict(extra="forbid")

    jurisprudence_document_id: str = Field(min_length=3, max_length=200)
    original_filename: str = Field(min_length=1, max_length=500)
    media_type: str = Field(default="application/pdf", pattern=r"^application/pdf$")
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    ingestion_status: JurisprudenceIngestionStatus = JurisprudenceIngestionStatus.READY
    text_extracted: Literal[True] = True
    extracted_characters: int = Field(ge=1)
    page_count: int = Field(ge=1)
    chunk_count: int = Field(ge=1)
    source_scope: JurisprudenceSourceScope = JurisprudenceSourceScope.SESSION
    user_attached: Literal[True] = True
    persistent_corpus_member: Literal[False] = False
    source_type: Literal[SourceType.JURISPRUDENCIA] = SourceType.JURISPRUDENCIA
    processed_at_utc: str = Field(min_length=1, max_length=80)
    warnings: list[str] = Field(default_factory=list)

    # Fronteras expresas de E.1. Se habilitarán, en su caso, en subbloques posteriores.
    authenticity_verified: Literal[False] = False
    temporal_validity_verified: Literal[False] = False
    legal_applicability_evaluated: Literal[False] = False
    can_control_legal_decision: Literal[False] = False


class JurisprudenceIngestionResult(BaseModel):
    """Resultado completo de E.1, manteniendo el ProcessedDocument histórico."""

    model_config = ConfigDict(extra="forbid")

    document: ProcessedDocument
    chunks: list[LegalChunk] = Field(min_length=1)
    chunking_report: ChunkingReport
    receipt: JurisprudenceIngestionReceipt
