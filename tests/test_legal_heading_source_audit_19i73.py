from __future__ import annotations

from app.domain.legal_chunks import LegalChunk, LegalUnitType
from app.services.legal_heading_source_audit import _find_source_line


def _chunk(text: str) -> LegalChunk:
    import hashlib

    return LegalChunk(
        chunk_id="cff:article:test",
        canonical_id="cff",
        source_role="normativa",
        document_type="law",
        title="CFF",
        unit_type=LegalUnitType.ARTICLE,
        unit_label="Artículo 31",
        hierarchy=[],
        source_sha256="a" * 64,
        text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        text=text,
    )


def test_find_exact_source_line() -> None:
    chunk = _chunk("Artículo 31.- Texto legítimo.\nSegundo párrafo.")
    lines = ["Anterior.", "", "Artículo 31.- Texto legítimo.", "Segundo párrafo."]
    number, source, previous, following = _find_source_line(
        lines=lines,
        chunk=chunk,
    )
    assert number == 3
    assert source == "Artículo 31.- Texto legítimo."
    assert previous == ""
    assert following == "Segundo párrafo."


def test_find_source_line_with_whitespace_normalization() -> None:
    chunk = _chunk("Artículo 31.- Texto   legítimo con espacios.")
    lines = ["Artículo 31.- Texto legítimo con espacios."]
    number, source, _, _ = _find_source_line(lines=lines, chunk=chunk)
    assert number == 1
    assert source is not None
