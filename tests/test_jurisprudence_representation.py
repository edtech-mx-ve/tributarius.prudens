from pathlib import Path

import pytest

from app.domain.documents import (
    DocumentMetadata,
    ExtractionStats,
    ProcessedDocument,
    SourceType,
)
from app.services.document_pipeline import ExtractedPage, build_markdown
from app.services.jurisprudence_representation import (
    JurisprudenceRepresentationError,
    represent_jurisprudence_document,
)

SHA256 = "a" * 64


def _document(
    *,
    source_type: SourceType = SourceType.JURISPRUDENCIA,
    pages: list[ExtractedPage] | None = None,
) -> ProcessedDocument:
    source_pages = pages or [
        ExtractedPage(number=1, text="TESIS DE PRUEBA\nPrimer criterio."),
        ExtractedPage(number=2, text="Continuación del criterio."),
    ]
    markdown, headings, empty_pages = build_markdown("Tesis de prueba", source_pages)
    extracted = sum(len(page.text.strip()) for page in source_pages)
    return ProcessedDocument(
        metadata=DocumentMetadata(
            document_id="jurisprudencia-test",
            source_type=source_type,
            original_filename="tesis.pdf",
            source_path=str(Path("tesis.pdf")),
            normalized_path=str(Path("tesis.md")),
            sha256=SHA256,
            processed_at_utc="2026-09-01T00:00:00+00:00",
            extractor="pypdf",
            extractor_version="test",
            stats=ExtractionStats(
                page_count=len(source_pages),
                extracted_characters=extracted,
                empty_pages=empty_pages,
                heading_count=headings,
            ),
        ),
        markdown=markdown,
    )


def test_representation_preserves_document_provenance() -> None:
    result = represent_jurisprudence_document(_document())

    assert result.document_id == "jurisprudencia-test"
    assert result.original_filename == "tesis.pdf"
    assert result.source_sha256 == SHA256
    assert result.page_count == 2


def test_representation_preserves_page_boundaries_and_text() -> None:
    result = represent_jurisprudence_document(_document())

    assert [page.number for page in result.pages] == [1, 2]
    assert result.pages[0].has_extractable_text is True
    assert "TESIS DE PRUEBA" in result.pages[0].text
    assert "Primer criterio." in result.full_text
    assert "Continuación del criterio." in result.full_text


def test_representation_marks_empty_page_without_promoting_placeholder() -> None:
    result = represent_jurisprudence_document(
        _document(
            pages=[
                ExtractedPage(number=1, text="Criterio útil."),
                ExtractedPage(number=2, text=""),
            ]
        )
    )

    assert result.pages[1].has_extractable_text is False
    assert result.pages[1].text == ""
    assert "Página sin texto extraíble" not in result.full_text


def test_representation_rejects_non_jurisprudential_document() -> None:
    with pytest.raises(
        JurisprudenceRepresentationError,
        match="tipificado como jurisprudencia",
    ):
        represent_jurisprudence_document(_document(source_type=SourceType.NORMATIVA))


def test_representation_fails_closed_when_page_trace_is_incomplete() -> None:
    document = _document()
    damaged = document.model_copy(
        update={"markdown": document.markdown.replace("<!-- page:2 -->", "")}
    )

    with pytest.raises(
        JurisprudenceRepresentationError,
        match="no conserva todas las páginas",
    ):
        represent_jurisprudence_document(damaged)
