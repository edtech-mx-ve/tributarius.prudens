from __future__ import annotations

import hashlib
from pathlib import Path

from app.domain.legal_chunks import LegalChunk, LegalUnitType
from app.services.legal_duplicate_boundary_audit import (
    audit_duplicate_boundaries,
)


def _chunk(
    *,
    chunk_id: str,
    text: str,
    page_start: int,
    page_end: int,
) -> LegalChunk:
    return LegalChunk(
        chunk_id=chunk_id,
        canonical_id="cff",
        source_role="normativa",
        document_type="law",
        title="CFF",
        unit_type=LegalUnitType.ARTICLE,
        unit_label="Artículo 21",
        hierarchy=[],
        source_sha256="a" * 64,
        text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        text=text,
        page_start=page_start,
        page_end=page_end,
    )


def _write(path: Path, chunks: list[LegalChunk]) -> None:
    path.write_text(
        "".join(chunk.model_dump_json() + "\n" for chunk in chunks),
        encoding="utf-8",
    )


def test_full_containment_beats_shared_prefix_false_positives(
    tmp_path: Path,
) -> None:
    shared = "Artículo 21.- " + ("Prefijo común. " * 20)
    baseline_text = shared + ("Cuerpo baseline. " * 40)
    baseline = _chunk(
        chunk_id="baseline21",
        text=baseline_text,
        page_start=320,
        page_end=324,
    )
    early = _chunk(
        chunk_id="candidate001",
        text=shared + ("Otra versión. " * 20),
        page_start=33,
        page_end=34,
    )
    same_page_prefix = _chunk(
        chunk_id="candidate002",
        text=shared + ("Fragmento previo. " * 10),
        page_start=320,
        page_end=320,
    )
    containing = _chunk(
        chunk_id="candidate003",
        text=baseline_text + ("Contenido expandido. " * 10),
        page_start=320,
        page_end=336,
    )

    baseline_path = tmp_path / "baseline.jsonl"
    candidate_path = tmp_path / "candidate.jsonl"
    _write(baseline_path, [baseline])
    _write(candidate_path, [early, same_page_prefix, containing])

    report = audit_duplicate_boundaries(
        baseline_path=baseline_path,
        candidate_path=candidate_path,
    )
    assert report.total_ambiguous == 1
    assert report.unresolved == 0
    assert report.findings[0].classification == "resolved_unique_full_content"
    assert (
        report.findings[0].resolved_candidate_chunk_id
        == "candidate003"
    )
