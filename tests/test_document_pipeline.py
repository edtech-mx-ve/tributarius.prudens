from pathlib import Path

import pytest

from app.domain.documents import SourceType
from app.services.document_pipeline import (
    ExtractedPage,
    InvalidDocumentError,
    build_markdown,
    normalize_whitespace,
    safe_stem,
    structure_to_markdown,
    validate_pdf_path,
)


def test_normalize_whitespace_collapses_spaces_and_blank_lines() -> None:
    raw = "  ARTÍCULO   1  \r\n\r\n\r\n Texto   fiscal\tválido "
    assert normalize_whitespace(raw) == "ARTÍCULO 1\n\nTexto fiscal válido"


def test_structure_to_markdown_detects_legal_headings() -> None:
    text = "CAPÍTULO I\nDISPOSICIONES GENERALES\nARTÍCULO 1\nObjeto de la ley."
    markdown, count = structure_to_markdown(text)

    assert "## CAPÍTULO I" in markdown
    assert "## DISPOSICIONES GENERALES" in markdown
    assert "### ARTÍCULO 1" in markdown
    assert count == 3


def test_build_markdown_preserves_page_markers() -> None:
    pages = [
        ExtractedPage(number=1, text="ARTÍCULO 1\nContenido"),
        ExtractedPage(number=2, text=""),
    ]
    markdown, headings, empty_pages = build_markdown("Ley de prueba", pages)

    assert "# Ley de prueba" in markdown
    assert "<!-- page:1 -->" in markdown
    assert "<!-- page:2 -->" in markdown
    assert "_[Página sin texto extraíble]_" in markdown
    assert headings == 1
    assert empty_pages == 1


def test_safe_stem_removes_unsafe_characters() -> None:
    assert safe_stem("Ley Fiscal 2026 (Final).pdf") == "ley-fiscal-2026-final"


def test_validate_pdf_rejects_non_pdf(tmp_path: Path) -> None:
    file_path = tmp_path / "texto.txt"
    file_path.write_text("contenido", encoding="utf-8")

    with pytest.raises(InvalidDocumentError, match="Solo se aceptan archivos PDF"):
        validate_pdf_path(file_path)


def test_source_type_values_are_stable() -> None:
    assert SourceType.NORMATIVA.value == "normativa"
    assert SourceType.JURISPRUDENCIA.value == "jurisprudencia"
