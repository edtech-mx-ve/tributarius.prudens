from __future__ import annotations

from pathlib import Path

from app.domain.legal_chunks import LegalChunk, LegalUnitType
from app.services.semantic_delta_audit import audit_semantic_delta


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


def test_reference_like_boundary_absorbed_by_candidate(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.jsonl"
    candidate_path = tmp_path / "candidate.jsonl"

    part_a = "Artículo 30.- Cuerpo principal " + ("A" * 80)
    part_b = "artículo 31-A de este Código " + ("B" * 80)
    baseline = [
        _chunk(chunk_id="cff:0001", label="Artículo 30", text=part_a),
        _chunk(
            chunk_id="cff:0002",
            label="Artículo 31-A de",
            text=part_b,
        ),
    ]
    candidate = [
        _chunk(
            chunk_id="cff:1001",
            label="Artículo 30",
            text=part_a + "\n" + part_b,
        )
    ]
    _write(baseline_path, baseline)
    _write(candidate_path, candidate)

    report = audit_semantic_delta(
        baseline_path=baseline_path,
        candidate_path=candidate_path,
    )

    classifications = {
        item.chunk_id: item.classification for item in report.removed
    }
    assert classifications["cff:0002"] == "absorbed_reference_like_boundary"


def test_numeric_article_loss_requires_review(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.jsonl"
    candidate_path = tmp_path / "candidate.jsonl"
    baseline = [
        _chunk(
            chunk_id="cff:0003",
            label="Artículo 31",
            text="Artículo 31.- Texto legítimo " + ("C" * 80),
        )
    ]
    candidate: list[LegalChunk] = []
    _write(baseline_path, baseline)
    _write(candidate_path, candidate)

    report = audit_semantic_delta(
        baseline_path=baseline_path,
        candidate_path=candidate_path,
    )

    assert report.removed[0].classification == (
        "missing_numeric_article_requires_review"
    )
