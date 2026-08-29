import hashlib
import json
from pathlib import Path

import pytest

import app.services.public_runtime_acceptance_19i18l as m


def test_exact_document_coverage() -> None:
    assert {item.document_id for item in m.decisions()} == m.DOCS
    assert len(m.decisions()) == 14


def test_rebuilt_provenance_is_explicit() -> None:
    by_id = {item.document_id: item for item in m.decisions()}
    for document_id in ("lfdc", "reg_liva_250914"):
        assert (
            by_id[document_id].provenance_status
            == "official_rebuild_chain_verified"
        )
        assert "J12.4" in by_id[document_id].provenance_chain


def test_temporal_unknown_is_fail_closed() -> None:
    by_id = {item.document_id: item for item in m.decisions()}
    assert (
        by_id["cff"].temporal_status
        == "temporal_evidence_incomplete_fail_closed"
    )
    assert (
        by_id["lif_2026"].temporal_status
        == "temporal_evidence_registered"
    )
    assert (
        by_id["rmf_2026"].temporal_status
        == "temporal_evidence_registered"
    )


def test_acceptance_does_not_auto_publish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = tmp_path / "r"
    canonical_dir = runtime / "canonical"
    canonical_dir.mkdir(parents=True)
    canonical = canonical_dir / "c.jsonl"
    canonical.write_text("{}\n", encoding="utf-8")
    sha256 = hashlib.sha256(canonical.read_bytes()).hexdigest()

    monkeypatch.setattr(m, "PUBLIC_SHA", sha256)
    acceptance = {
        "canonical_sha256": sha256,
        "parent_count": 2962,
        "normative_document_count": 14,
        "benchmark_passed": True,
        "blocked_content_absent": True,
        "technical_local_acceptance": True,
    }
    (runtime / "public_safe_runtime_acceptance.json").write_text(
        json.dumps(acceptance),
        encoding="utf-8",
    )

    report = m.execute(runtime, tmp_path / "out.json")
    assert report["provenance_complete"] is True
    assert report["temporal_fail_closed_complete"] is True
    assert report["temporal_validity_complete"] is False
    assert report["redistribution_human_review_required"] is True
    assert report["public_release_allowed"] is False
