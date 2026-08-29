from __future__ import annotations

import hashlib

from app.domain.legal_chunks import LegalChunk, LegalUnitType
from app.services.legal_duplicate_boundary_audit import (
    _full_content_match,
    _page_overlap,
)


def _chunk(
    *,
    chunk_id: str,
    label: str,
    text: str,
    page_start: int | None = None,
    page_end: int | None = None,
) -> LegalChunk:
    return LegalChunk(
        chunk_id=chunk_id,
        canonical_id="cff",
        source_role="normativa",
        document_type="law",
        title="CFF",
        unit_type=LegalUnitType.ARTICLE,
        unit_label=label,
        hierarchy=[],
        source_sha256="a" * 64,
        text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        text=text,
        page_start=page_start,
        page_end=page_end,
    )


def test_content_match_accepts_expanded_candidate() -> None:
    old = _chunk(
        chunk_id="old00001",
        label="Artículo 31",
        text="Artículo 31.- " + ("Texto jurídico. " * 12),
    )
    candidate = _chunk(
        chunk_id="new00001",
        label="Artículo 31",
        text=old.text + " Referencia reintegrada.",
    )
    assert _full_content_match(old, candidate)


def test_page_overlap_detects_unique_range() -> None:
    old = _chunk(
        chunk_id="old00002",
        label="Artículo 31",
        text="Artículo 31.- Texto.",
        page_start=10,
        page_end=11,
    )
    candidate = _chunk(
        chunk_id="new00002",
        label="Artículo 31",
        text="Artículo 31.- Texto ampliado.",
        page_start=11,
        page_end=12,
    )
    other = _chunk(
        chunk_id="oth00002",
        label="Artículo 31",
        text="Artículo 31.- Otro.",
        page_start=30,
        page_end=31,
    )
    assert _page_overlap(old, candidate)
    assert not _page_overlap(old, other)
