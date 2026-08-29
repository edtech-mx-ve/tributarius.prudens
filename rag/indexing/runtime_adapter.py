from __future__ import annotations

from app.domain.chunks import (
    ChunkMetadata,
    LegalChunkType,
    LegalHierarchy,
)
from app.domain.chunks import (
    LegalChunk as RuntimeLegalChunk,
)
from app.domain.documents import SourceType
from app.domain.legal_chunks import LegalChunk as CorpusLegalChunk
from app.domain.legal_chunks import LegalUnitType


class RuntimeChunkAdapterError(RuntimeError):
    """Error controlado al adaptar chunks del corpus 19C al esquema de runtime."""


def _source_type(chunk: CorpusLegalChunk) -> SourceType:
    if chunk.canonical_id == "prodecon_contribuyente":
        return SourceType.PRODECON
    if chunk.canonical_id == "manual_derecho_fiscal_unam":
        return SourceType.UNAM
    return SourceType.NORMATIVA


def _runtime_chunk_type(unit_type: LegalUnitType) -> LegalChunkType:
    mapping = {
        LegalUnitType.ARTICLE: LegalChunkType.ARTICLE,
        LegalUnitType.ACADEMIC_CHAPTER: LegalChunkType.CHAPTER,
        LegalUnitType.ADMINISTRATIVE_RULE: LegalChunkType.SECTION,
        LegalUnitType.PRODECON_SECTION: LegalChunkType.SECTION,
        LegalUnitType.STRUCTURAL_SECTION: LegalChunkType.SECTION,
    }
    return mapping[unit_type]


def _hierarchy(chunk: CorpusLegalChunk) -> LegalHierarchy:
    values = [item.strip() for item in chunk.hierarchy if item.strip()]
    article = chunk.unit_label if chunk.unit_type is LegalUnitType.ARTICLE else None
    chapter = (
        chunk.unit_label
        if chunk.unit_type is LegalUnitType.ACADEMIC_CHAPTER
        else next((item for item in values if "capítulo" in item.lower()), None)
    )
    section = (
        chunk.unit_label
        if chunk.unit_type
        in {
            LegalUnitType.ADMINISTRATIVE_RULE,
            LegalUnitType.PRODECON_SECTION,
            LegalUnitType.STRUCTURAL_SECTION,
        }
        else next((item for item in values if "sección" in item.lower()), None)
    )
    title = next((item for item in values if "título" in item.lower()), None)

    return LegalHierarchy(
        title=title,
        chapter=chapter,
        section=section,
        article=article,
    )


def _version_label(chunk: CorpusLegalChunk) -> str | None:
    if chunk.fiscal_year is not None:
        return str(chunk.fiscal_year)
    return (
        chunk.last_reform_date
        or chunk.publication_date
        or chunk.effective_from
    )


def adapt_corpus_chunk(
    chunk: CorpusLegalChunk,
    *,
    chunk_index: int,
) -> RuntimeLegalChunk:
    if chunk_index < 0:
        raise RuntimeChunkAdapterError("chunk_index debe ser >= 0.")

    return RuntimeLegalChunk(
        chunk_id=chunk.chunk_id,
        text=chunk.text,
        metadata=ChunkMetadata(
            document_id=chunk.canonical_id,
            source_type=_source_type(chunk),
            source_filename=f"{chunk.canonical_id}.md",
            chunk_index=chunk_index,
            chunk_type=_runtime_chunk_type(chunk.unit_type),
            legal_identifier=chunk.unit_label,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            hierarchy=_hierarchy(chunk),
            source_sha256=chunk.source_sha256,
            fiscal_year=chunk.fiscal_year,
            version_label=_version_label(chunk),
            canonical_id=chunk.canonical_id,
            source_role=chunk.source_role,
            document_type=chunk.document_type,
            title=chunk.title,
            source_unit_type=chunk.unit_type.value,
            source_unit_label=chunk.unit_label,
            matter=list(chunk.matter),
            jurisdiction=chunk.jurisdiction,
            publication_date=chunk.publication_date,
            last_reform_date=chunk.last_reform_date,
            effective_from=chunk.effective_from,
            effective_to=chunk.effective_to,
            text_sha256=chunk.text_sha256,
        ),
    )
