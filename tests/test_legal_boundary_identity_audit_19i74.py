from __future__ import annotations

import hashlib
from pathlib import Path

from app.domain.legal_chunks import LegalChunk, LegalUnitType
from app.services.legal_boundary_identity_audit import audit_boundary_identity


def _chunk(*, chunk_id: str, label: str, text: str) -> LegalChunk:
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
    )


def _write(path: Path, chunks: list[LegalChunk]) -> None:
    path.write_text(
        "".join(chunk.model_dump_json() + "\n" for chunk in chunks),
        encoding="utf-8",
    )


def test_same_boundary_with_expanded_text_is_preserved(tmp_path: Path) -> None:
    old = _chunk(
        chunk_id="cff:old31",
        label="Artículo 31",
        text="Artículo 31.- " + ("Texto legítimo. " * 8),
    )
    candidate_same = _chunk(
        chunk_id="cff:new31",
        label="Artículo 31",
        text=old.text + "\nReferencia que antes abrió falso límite.",
    )
    # Add a previous unit so 19I.7.2 can observe absorption.
    previous = _chunk(
        chunk_id="cff:old30",
        label="Artículo 30",
        text="Artículo 30.- " + ("Previo. " * 8),
    )
    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    _write(baseline, [previous, old])
    _write(candidate, [previous, candidate_same])

    report = audit_boundary_identity(
        baseline_path=baseline,
        candidate_path=candidate,
    )
    assert report.preserved_boundary_identity == 1
    assert report.missing_boundary_identity == 0


def test_missing_same_label_is_flagged(tmp_path: Path) -> None:
    old = _chunk(
        chunk_id="cff:old31",
        label="Artículo 31",
        text="Artículo 31.- " + ("Texto legítimo. " * 8),
    )
    merged = _chunk(
        chunk_id="cff:new30",
        label="Artículo 30",
        text="Artículo 30.- Previo.\n" + old.text,
    )
    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    _write(baseline, [old])
    _write(candidate, [merged])

    report = audit_boundary_identity(
        baseline_path=baseline,
        candidate_path=candidate,
    )
    assert report.missing_boundary_identity == 1
