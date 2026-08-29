from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from app.services.sprint19_local_acceptance_audit import (
    Sprint19LocalAcceptancePaths,
    audit_sprint19_local_acceptance,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_fixture(tmp_path: Path) -> Sprint19LocalAcceptancePaths:
    semantic_corpus = tmp_path / "chunks_semantic_v2.jsonl"
    semantic_corpus.write_text(
        "\n".join(json.dumps({"id": index}) for index in range(2)) + "\n",
        encoding="utf-8",
    )
    semantic_manifest = tmp_path / "semantic_manifest.json"
    semantic_manifest.write_text(
        json.dumps(
            {
                "status": "approved_semantic_canonical",
                "promoted_chunks": 2,
                "document_count": 1,
                "promoted_sha256": _sha256(semantic_corpus),
            }
        ),
        encoding="utf-8",
    )

    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    index_path = runtime_dir / "index.faiss"
    chunks_path = runtime_dir / "chunks.jsonl"
    index_path.write_bytes(b"fake-index")
    chunks_path.write_text("{}\n{}\n{}\n", encoding="utf-8")
    runtime_manifest = {
        "schema_version": "1.0",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "model_name": "test-model",
        "vector_dimension": 8,
        "metric": "cosine_via_inner_product",
        "normalized": True,
        "chunk_count": 3,
        "source_chunk_files": ["fixture.jsonl"],
        "index_filename": "index.faiss",
        "chunks_filename": "chunks.jsonl",
        "index_sha256": _sha256(index_path),
        "chunks_sha256": _sha256(chunks_path),
    }
    (runtime_dir / "manifest.json").write_text(
        json.dumps(runtime_manifest),
        encoding="utf-8",
    )

    temporal_registry = tmp_path / "temporal.json"
    temporal_registry.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "source_sprint": "19I.13",
                "policy": "fail-closed",
                "entries": [
                    {
                        "canonical_id": "cpeum",
                        "effective_from": None,
                        "effective_to": None,
                        "document_wide_applicable": False,
                    }
                ],
                "coverage_gaps": [
                    {
                        "canonical_id": "liva",
                        "gap_type": "document_wide_temporal_validity",
                        "status": "unknown_fail_closed",
                    },
                    {
                        "canonical_id": "cpeum",
                        "gap_type": "document_wide_temporal_validity",
                        "status": "unknown_fail_closed",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return Sprint19LocalAcceptancePaths(
        semantic_corpus=semantic_corpus,
        semantic_manifest=semantic_manifest,
        runtime_dir=runtime_dir,
        temporal_registry=temporal_registry,
    )


def test_integral_gate_accepts_consistent_fixture(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path)

    result = audit_sprint19_local_acceptance(
        paths=paths,
        expected_semantic_parents=2,
        expected_semantic_documents=1,
        expected_runtime_chunks=3,
        expected_vector_dimension=8,
        expected_model_name="test-model",
    )

    assert result.failures == ()
    assert result.temporal_blocked_documents == ("cpeum", "liva")


def test_integral_gate_rejects_runtime_hash_mismatch(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path)
    (paths.runtime_dir / "index.faiss").write_bytes(b"tampered")

    result = audit_sprint19_local_acceptance(
        paths=paths,
        expected_semantic_parents=2,
        expected_semantic_documents=1,
        expected_runtime_chunks=3,
        expected_vector_dimension=8,
        expected_model_name="test-model",
    )

    assert "runtime_index_sha256_mismatch" in result.failures


def test_integral_gate_rejects_promoted_temporal_date(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path)
    payload = json.loads(paths.temporal_registry.read_text(encoding="utf-8"))
    payload["entries"][0]["effective_from"] = "2026-01-01"
    paths.temporal_registry.write_text(json.dumps(payload), encoding="utf-8")

    result = audit_sprint19_local_acceptance(
        paths=paths,
        expected_semantic_parents=2,
        expected_semantic_documents=1,
        expected_runtime_chunks=3,
        expected_vector_dimension=8,
        expected_model_name="test-model",
    )

    assert "temporal_entry_effective_from_not_null" in result.failures
