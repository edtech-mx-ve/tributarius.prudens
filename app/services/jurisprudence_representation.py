from __future__ import annotations

import re

from app.domain.documents import ProcessedDocument, SourceType
from app.domain.jurisprudence_document import (
    JurisprudenceDocumentRepresentation,
    JurisprudencePage,
)
from app.services.document_pipeline import normalize_whitespace

PAGE_MARKER_RE = re.compile(
    r"<!-- page:(?P<number>\d+) -->\n## Página (?P=number)\n\n"
    r"(?P<text>.*?)(?=\n\n<!-- page:\d+ -->|\Z)",
    flags=re.DOTALL,
)
EMPTY_PAGE_MARKER = "_[Página sin texto extraíble]_"


class JurisprudenceRepresentationError(ValueError):
    """El documento procesado no puede representarse como jurisprudencia."""


def _plain_page_text(markdown_text: str) -> str:
    if markdown_text.strip() == EMPTY_PAGE_MARKER:
        return ""

    lines: list[str] = []
    for line in markdown_text.splitlines():
        cleaned = re.sub(r"^#{1,6}\s+", "", line).strip()
        if cleaned:
            lines.append(cleaned)
    return normalize_whitespace("\n".join(lines))


def represent_jurisprudence_document(
    document: ProcessedDocument,
) -> JurisprudenceDocumentRepresentation:
    """Convierte la salida del pipeline en representación paginada trazable."""
    if document.metadata.source_type is not SourceType.JURISPRUDENCIA:
        raise JurisprudenceRepresentationError(
            "Solo puede representarse un documento tipificado como jurisprudencia."
        )

    pages: list[JurisprudencePage] = []
    for match in PAGE_MARKER_RE.finditer(document.markdown):
        page_text = _plain_page_text(match.group("text"))
        pages.append(
            JurisprudencePage(
                number=int(match.group("number")),
                text=page_text,
                has_extractable_text=bool(page_text),
            )
        )

    expected_pages = document.metadata.stats.page_count
    if len(pages) != expected_pages:
        raise JurisprudenceRepresentationError(
            "La representación no conserva todas las páginas declaradas "
            f"({len(pages)} de {expected_pages})."
        )

    expected_numbers = list(range(1, expected_pages + 1))
    actual_numbers = [page.number for page in pages]
    if actual_numbers != expected_numbers:
        raise JurisprudenceRepresentationError(
            "Los marcadores de página no forman una secuencia íntegra."
        )

    full_text = normalize_whitespace(
        "\n\n".join(page.text for page in pages if page.has_extractable_text)
    )
    if not full_text:
        raise JurisprudenceRepresentationError(
            "El documento jurisprudencial no contiene texto representable."
        )

    return JurisprudenceDocumentRepresentation(
        document_id=document.metadata.document_id,
        original_filename=document.metadata.original_filename,
        source_sha256=document.metadata.sha256,
        page_count=expected_pages,
        extracted_characters=document.metadata.stats.extracted_characters,
        pages=pages,
        full_text=full_text,
        warnings=list(document.metadata.warnings),
    )
