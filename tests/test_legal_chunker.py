from pathlib import Path

import pytest

from app.domain.chunks import LegalChunkType
from app.domain.documents import (
    DocumentMetadata,
    ExtractionStats,
    SourceType,
)
from app.services.legal_chunker import (
    ChunkingError,
    build_chunks,
    classify_heading,
    parse_legal_blocks,
    write_chunks_jsonl,
)


def make_metadata() -> DocumentMetadata:
    return DocumentMetadata(
        document_id="normativa-1234567890abcdef",
        source_type=SourceType.NORMATIVA,
        original_filename="ley-prueba.pdf",
        source_path="knowledge/sources/normativa/ley-prueba.pdf",
        normalized_path="knowledge/normalized/normativa/ley-prueba.md",
        sha256="a" * 64,
        processed_at_utc="2026-08-27T00:00:00+00:00",
        extractor="pypdf",
        extractor_version="5.9.0",
        stats=ExtractionStats(
            page_count=2,
            extracted_characters=100,
            empty_pages=0,
            heading_count=4,
        ),
    )


def sample_markdown() -> str:
    return """# Ley de prueba

> Documento normalizado por Tributarius prudens.

<!-- page:1 -->
## Página 1

## TÍTULO PRIMERO
## CAPÍTULO I
### ARTÍCULO 1
Objeto general de la disposición.

I. Primera obligación.
a) Primer supuesto.

<!-- page:2 -->
## Página 2

### ARTÍCULO 2
Segundo contenido.
"""


def test_classify_heading_recognizes_legal_levels() -> None:
    assert classify_heading("TÍTULO PRIMERO")[0] is LegalChunkType.TITLE
    assert classify_heading("CAPÍTULO I")[0] is LegalChunkType.CHAPTER
    assert classify_heading("SECCIÓN II")[0] is LegalChunkType.SECTION
    assert classify_heading("ARTÍCULO 15-BIS")[0] is LegalChunkType.ARTICLE


def test_parse_blocks_preserves_page_and_hierarchy() -> None:
    blocks, pages = parse_legal_blocks(sample_markdown())

    article = next(block for block in blocks if block.block_type is LegalChunkType.ARTICLE)
    fraction = next(block for block in blocks if block.block_type is LegalChunkType.FRACTION)
    subsection = next(
        block for block in blocks if block.block_type is LegalChunkType.SUBSECTION
    )

    assert pages == [1, 2]
    assert article.page == 1
    assert article.legal_identifier == "1"
    assert fraction.hierarchy.article == "1"
    assert fraction.hierarchy.fraction == "I"
    assert subsection.hierarchy.subsection == "a"


def test_build_chunks_is_deterministic() -> None:
    metadata = make_metadata()

    first, first_report = build_chunks(sample_markdown(), metadata)
    second, second_report = build_chunks(sample_markdown(), metadata)

    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
    assert first_report.chunk_count == second_report.chunk_count
    assert first_report.pages_seen == [1, 2]


def test_build_chunks_carries_source_traceability() -> None:
    chunks, report = build_chunks(sample_markdown(), make_metadata())

    assert report.chunk_count > 0
    assert chunks[0].metadata.document_id == "normativa-1234567890abcdef"
    assert chunks[0].metadata.source_sha256 == "a" * 64
    assert chunks[0].metadata.source_type is SourceType.NORMATIVA


def test_build_chunks_detects_articles_and_subunits() -> None:
    chunks, report = build_chunks(sample_markdown(), make_metadata())

    assert report.by_type["article"] == 2
    assert report.by_type["fraction"] == 1
    assert report.by_type["subsection"] == 1


def test_build_chunks_rejects_too_small_limit() -> None:
    with pytest.raises(ChunkingError, match="al menos 500"):
        build_chunks(sample_markdown(), make_metadata(), max_characters=100)


def test_write_chunks_refuses_silent_overwrite(tmp_path: Path) -> None:
    chunks, _ = build_chunks(sample_markdown(), make_metadata())
    target = tmp_path / "chunks.jsonl"

    write_chunks_jsonl(chunks, target)

    with pytest.raises(ChunkingError, match="Ya existe"):
        write_chunks_jsonl(chunks, target)


def test_write_chunks_allows_explicit_overwrite(tmp_path: Path) -> None:
    chunks, _ = build_chunks(sample_markdown(), make_metadata())
    target = tmp_path / "chunks.jsonl"

    write_chunks_jsonl(chunks, target)
    result = write_chunks_jsonl(chunks, target, overwrite=True)

    assert result == target.resolve()
    assert target.read_text(encoding="utf-8").count("\n") == len(chunks)


def test_missing_page_markers_produces_warning() -> None:
    markdown = "## CAPÍTULO I\n### ARTÍCULO 1\nContenido."
    _, report = build_chunks(markdown, make_metadata())

    assert "No se encontraron marcadores de página del Sprint 1." in report.warnings
