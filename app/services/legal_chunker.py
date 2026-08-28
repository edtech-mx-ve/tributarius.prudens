from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from app.domain.chunks import (
    ChunkingReport,
    ChunkMetadata,
    LegalChunk,
    LegalChunkType,
    LegalHierarchy,
)
from app.domain.documents import DocumentMetadata

logger = logging.getLogger(__name__)

PAGE_MARKER_RE = re.compile(r"^<!--\s*page:(\d+)\s*-->$")
MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

TITLE_RE = re.compile(r"^T[ÍI]TULO\b", re.IGNORECASE)
CHAPTER_RE = re.compile(r"^CAP[ÍI]TULO\b", re.IGNORECASE)
SECTION_RE = re.compile(r"^(SECCI[ÓO]N|SUBSECCI[ÓO]N)\b", re.IGNORECASE)
ARTICLE_RE = re.compile(
    r"^(ART[ÍI]CULO|ART\.)\s+([0-9]+(?:-[A-Z0-9]+)?(?:\s+BIS|\s+TER|\s+QU[ÁA]TER)?)\b",
    re.IGNORECASE,
)
FRACTION_RE = re.compile(
    r"^(?P<label>(?:[IVXLCDM]+|\d+))[\.\)]\s+(?P<body>.+)$",
    re.IGNORECASE,
)
SUBSECTION_RE = re.compile(
    r"^(?P<label>[a-záéíóúñ])[\)\.]\s+(?P<body>.+)$",
    re.IGNORECASE,
)

SYNTHETIC_PAGE_HEADING_RE = re.compile(r"^P[ÁA]GINA\s+\d+$", re.IGNORECASE)
PLACEHOLDER_PAGE_RE = re.compile(r"^_\[P[ÁA]GINA SIN TEXTO EXTRA[ÍI]BLE\]_$", re.IGNORECASE)

MAX_CHUNK_CHARACTERS = 6000


class ChunkingError(RuntimeError):
    """Error controlado durante el chunking jurídico."""


@dataclass(frozen=True)
class ParsedBlock:
    block_type: LegalChunkType
    text: str
    page: int | None
    hierarchy: LegalHierarchy
    legal_identifier: str | None


def _safe_load_metadata(path: Path) -> DocumentMetadata:
    resolved = path.expanduser().resolve()
    if not resolved.exists() or not resolved.is_file():
        raise ChunkingError(f"No existe el archivo de metadatos: {resolved}")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        return DocumentMetadata.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ChunkingError("Los metadatos documentales no son válidos.") from exc


def _safe_load_markdown(path: Path) -> str:
    resolved = path.expanduser().resolve()
    if not resolved.exists() or not resolved.is_file():
        raise ChunkingError(f"No existe el Markdown: {resolved}")
    if resolved.suffix.lower() != ".md":
        raise ChunkingError("El archivo normalizado debe ser Markdown (.md).")
    try:
        text = resolved.read_text(encoding="utf-8")
    except OSError as exc:
        raise ChunkingError("No fue posible leer el Markdown.") from exc
    if not text.strip():
        raise ChunkingError("El Markdown está vacío.")
    return text


def classify_heading(text: str) -> tuple[LegalChunkType, str | None]:
    normalized = text.strip()
    if TITLE_RE.match(normalized):
        return LegalChunkType.TITLE, normalized
    if CHAPTER_RE.match(normalized):
        return LegalChunkType.CHAPTER, normalized
    if SECTION_RE.match(normalized):
        return LegalChunkType.SECTION, normalized

    article_match = ARTICLE_RE.match(normalized)
    if article_match:
        return LegalChunkType.ARTICLE, article_match.group(2).upper()

    return LegalChunkType.PARAGRAPH, None


def _parse_inline_subunit(line: str) -> tuple[LegalChunkType, str | None] | None:
    fraction = FRACTION_RE.match(line)
    if fraction:
        return LegalChunkType.FRACTION, fraction.group("label").upper()

    subsection = SUBSECTION_RE.match(line)
    if subsection:
        return LegalChunkType.SUBSECTION, subsection.group("label").lower()

    return None


def _updated_hierarchy(
    hierarchy: LegalHierarchy,
    block_type: LegalChunkType,
    text: str,
    legal_identifier: str | None,
) -> LegalHierarchy:
    data = hierarchy.model_dump()

    if block_type is LegalChunkType.TITLE:
        data.update(
            title=text,
            chapter=None,
            section=None,
            article=None,
            fraction=None,
            subsection=None,
        )
    elif block_type is LegalChunkType.CHAPTER:
        data.update(
            chapter=text,
            section=None,
            article=None,
            fraction=None,
            subsection=None,
        )
    elif block_type is LegalChunkType.SECTION:
        data.update(section=text, article=None, fraction=None, subsection=None)
    elif block_type is LegalChunkType.ARTICLE:
        data.update(article=legal_identifier or text, fraction=None, subsection=None)
    elif block_type is LegalChunkType.FRACTION:
        data.update(fraction=legal_identifier, subsection=None)
    elif block_type is LegalChunkType.SUBSECTION:
        data.update(subsection=legal_identifier)

    return LegalHierarchy(**data)


def parse_legal_blocks(markdown: str) -> tuple[list[ParsedBlock], list[int]]:
    blocks: list[ParsedBlock] = []
    current_page: int | None = None
    pages_seen: list[int] = []
    hierarchy = LegalHierarchy()
    pending_lines: list[str] = []
    pending_page: int | None = None

    def flush_paragraph() -> None:
        nonlocal pending_lines, pending_page
        text = "\n".join(pending_lines).strip()
        if text and not PLACEHOLDER_PAGE_RE.match(text):
            blocks.append(
                ParsedBlock(
                    block_type=LegalChunkType.PARAGRAPH,
                    text=text,
                    page=pending_page,
                    hierarchy=hierarchy.model_copy(deep=True),
                    legal_identifier=None,
                )
            )
        pending_lines = []
        pending_page = None

    for raw_line in markdown.splitlines():
        line = raw_line.strip()

        page_match = PAGE_MARKER_RE.match(line)
        if page_match:
            flush_paragraph()
            current_page = int(page_match.group(1))
            if current_page not in pages_seen:
                pages_seen.append(current_page)
            continue

        if not line:
            flush_paragraph()
            continue

        heading_match = MARKDOWN_HEADING_RE.match(line)
        if heading_match:
            heading_text = heading_match.group(2).strip()
            if SYNTHETIC_PAGE_HEADING_RE.match(heading_text):
                continue

            flush_paragraph()
            block_type, legal_identifier = classify_heading(heading_text)

            # The document title generated by Sprint 1 is structural context,
            # not a retrievable legal unit by itself.
            if len(heading_match.group(1)) == 1 and block_type is LegalChunkType.PARAGRAPH:
                hierarchy = hierarchy.model_copy(deep=True)
                continue

            if block_type is not LegalChunkType.PARAGRAPH:
                hierarchy = _updated_hierarchy(
                    hierarchy,
                    block_type,
                    heading_text,
                    legal_identifier,
                )
                blocks.append(
                    ParsedBlock(
                        block_type=block_type,
                        text=heading_text,
                        page=current_page,
                        hierarchy=hierarchy.model_copy(deep=True),
                        legal_identifier=legal_identifier,
                    )
                )
            else:
                pending_lines = [heading_text]
                pending_page = current_page
            continue

        inline = _parse_inline_subunit(line)
        if inline is not None and hierarchy.article is not None:
            flush_paragraph()
            block_type, legal_identifier = inline
            hierarchy = _updated_hierarchy(
                hierarchy,
                block_type,
                line,
                legal_identifier,
            )
            blocks.append(
                ParsedBlock(
                    block_type=block_type,
                    text=line,
                    page=current_page,
                    hierarchy=hierarchy.model_copy(deep=True),
                    legal_identifier=legal_identifier,
                )
            )
            continue

        if pending_page is None:
            pending_page = current_page
        pending_lines.append(line)

    flush_paragraph()
    return blocks, pages_seen


def _split_oversized_text(text: str, max_characters: int) -> list[str]:
    if len(text) <= max_characters:
        return [text]

    paragraphs = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]
    if len(paragraphs) <= 1:
        paragraphs = [part.strip() for part in re.split(r"(?<=[.;:])\s+", text) if part.strip()]

    parts: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_characters:
            current = candidate
            continue

        if current:
            parts.append(current)

        if len(paragraph) <= max_characters:
            current = paragraph
            continue

        for start in range(0, len(paragraph), max_characters):
            parts.append(paragraph[start : start + max_characters].strip())
        current = ""

    if current:
        parts.append(current)
    return [part for part in parts if part]


def _chunk_id(document_id: str, index: int, text: str) -> str:
    fingerprint = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"{document_id}-chunk-{index:05d}-{fingerprint}"


def build_chunks(
    markdown: str,
    metadata: DocumentMetadata,
    *,
    max_characters: int = MAX_CHUNK_CHARACTERS,
) -> tuple[list[LegalChunk], ChunkingReport]:
    if max_characters < 500:
        raise ChunkingError("max_characters debe ser al menos 500.")

    blocks, pages_seen = parse_legal_blocks(markdown)
    chunks: list[LegalChunk] = []
    warnings: list[str] = []

    if not blocks:
        raise ChunkingError("No se detectaron bloques jurídicos recuperables.")

    for block in blocks:
        for part in _split_oversized_text(block.text, max_characters):
            index = len(chunks)
            chunks.append(
                LegalChunk(
                    chunk_id=_chunk_id(metadata.document_id, index, part),
                    text=part,
                    metadata=ChunkMetadata(
                        document_id=metadata.document_id,
                        source_type=metadata.source_type,
                        source_filename=metadata.original_filename,
                        chunk_index=index,
                        chunk_type=block.block_type,
                        legal_identifier=block.legal_identifier,
                        page_start=block.page,
                        page_end=block.page,
                        hierarchy=block.hierarchy,
                        source_sha256=metadata.sha256,
                    ),
                )
            )

    if not pages_seen:
        warnings.append("No se encontraron marcadores de página del Sprint 1.")
    if not any(chunk.metadata.chunk_type is LegalChunkType.ARTICLE for chunk in chunks):
        warnings.append("No se detectaron artículos explícitos.")

    counts = Counter(chunk.metadata.chunk_type.value for chunk in chunks)
    report = ChunkingReport(
        document_id=metadata.document_id,
        chunk_count=len(chunks),
        by_type=dict(sorted(counts.items())),
        pages_seen=pages_seen,
        warnings=warnings,
    )
    return chunks, report


def write_chunks_jsonl(
    chunks: list[LegalChunk],
    output_path: Path,
    *,
    overwrite: bool = False,
) -> Path:
    resolved = output_path.expanduser().resolve()
    if resolved.exists() and not overwrite:
        raise ChunkingError(
            f"Ya existe el archivo de chunks: {resolved}. "
            "Use --overwrite solo si desea regenerarlo deliberadamente."
        )
    resolved.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(
        chunk.model_dump_json(exclude_none=True) for chunk in chunks
    )
    resolved.write_text(payload + "\n", encoding="utf-8")
    return resolved


def chunk_document(
    markdown_path: Path,
    metadata_path: Path,
    output_path: Path,
    *,
    overwrite: bool = False,
    max_characters: int = MAX_CHUNK_CHARACTERS,
) -> ChunkingReport:
    markdown = _safe_load_markdown(markdown_path)
    metadata = _safe_load_metadata(metadata_path)

    chunks, report = build_chunks(
        markdown,
        metadata,
        max_characters=max_characters,
    )
    write_chunks_jsonl(chunks, output_path, overwrite=overwrite)

    logger.info(
        "Chunking completado: document_id=%s chunks=%s output=%s",
        report.document_id,
        report.chunk_count,
        output_path,
    )
    return report
