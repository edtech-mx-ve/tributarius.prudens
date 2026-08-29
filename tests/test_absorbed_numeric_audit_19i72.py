from __future__ import annotations

from pathlib import Path

from app.domain.legal_chunks import LegalChunk, LegalUnitType
from app.services.absorbed_numeric_audit import audit_absorbed_numeric


def _chunk(
    *,
    chunk_id: str,
    label: str,
    text: str,
    document: str = "cff",
) -> LegalChunk:
    import hashlib

    return LegalChunk(
        chunk_id=chunk_id,
        canonical_id=document,
        source_role="normativa",
        document_type="law",
        title=document.upper(),
        unit_type=LegalUnitType.ARTICLE,
        unit_label=label,
        hierarchy=[],
        source_sha256="a" * 64,
        text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        text=text,
    )


def _write(path: Path, chunks: list[LegalChunk]) -> None:
    path.write_text(
        "".join(chunk.model_dump_json() + "\n" for chunk in chunks),
        encoding="utf-8",
    )


def test_probable_legitimate_boundary_is_detected(tmp_path: Path) -> None:
    old = _chunk(
        chunk_id="cff:00000031",
        label="Artículo 31",
        text="Artículo 31.- " + ("Contenido jurídico. " * 12),
    )
    merged = _chunk(
        chunk_id="cff:10000030",
        label="Artículo 30",
        text="Artículo 30.- Previo.\n" + old.text,
    )

    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    _write(baseline, [old])
    _write(candidate, [merged])

    report = audit_absorbed_numeric(
        baseline_path=baseline,
        candidate_path=candidate,
    )
    assert report.findings[0].classification == (
        "probable_legitimate_article_boundary"
    )


def test_reference_like_line_is_false_boundary(tmp_path: Path) -> None:
    old = _chunk(
        chunk_id="cff:00000032",
        label="Artículo 31",
        text="Artículo 31 de este Código " + ("continúa referencia. " * 12),
    )
    merged = _chunk(
        chunk_id="cff:10000030",
        label="Artículo 30",
        text="Artículo 30.- Previo.\n" + old.text,
    )

    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    _write(baseline, [old])
    _write(candidate, [merged])

    report = audit_absorbed_numeric(
        baseline_path=baseline,
        candidate_path=candidate,
    )
    assert report.findings[0].classification == "reference_like_false_boundary"
