from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.services.runtime_release_bundle import (
    RuntimeReleaseBundleError,
    build_runtime_release_bundle,
    validate_runtime_release_bundle,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    index = runtime_dir / "index.faiss"
    chunks = runtime_dir / "chunks.jsonl"
    index.write_bytes(b"index-fixture")
    chunks.write_text("{}\n{}\n", encoding="utf-8")
    manifest = {
        "schema_version": "1.0",
        "created_at_utc": "2026-01-01T00:00:00+00:00",
        "model_name": "test-model",
        "vector_dimension": 8,
        "metric": "cosine_via_inner_product",
        "normalized": True,
        "chunk_count": 2,
        "source_chunk_files": ["fixture.jsonl"],
        "index_filename": "index.faiss",
        "chunks_filename": "chunks.jsonl",
        "index_sha256": _sha256(index),
        "chunks_sha256": _sha256(chunks),
    }
    (runtime_dir / "manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    temporal = tmp_path / "temporal.json"
    temporal.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "source_sprint": "19I.13",
                "policy": "fail-closed",
                "entries": [],
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
    return runtime_dir, temporal


def test_build_and_validate_bundle(tmp_path: Path) -> None:
    runtime_dir, temporal = _fixture(tmp_path)
    output = tmp_path / "bundle.zip"

    built = build_runtime_release_bundle(
        runtime_dir=runtime_dir,
        temporal_registry=temporal,
        output_path=output,
    )
    validated = validate_runtime_release_bundle(output)

    assert built.bundle_sha256 == validated.bundle_sha256
    assert validated.runtime_chunk_count == 2
    assert validated.runtime_vector_dimension == 8
    assert validated.temporal_blocked_documents == ("cpeum", "liva")


def test_bundle_is_deterministic(tmp_path: Path) -> None:
    runtime_dir, temporal = _fixture(tmp_path)
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"

    first_result = build_runtime_release_bundle(
        runtime_dir=runtime_dir,
        temporal_registry=temporal,
        output_path=first,
    )
    second_result = build_runtime_release_bundle(
        runtime_dir=runtime_dir,
        temporal_registry=temporal,
        output_path=second,
    )

    assert first_result.bundle_sha256 == second_result.bundle_sha256
    assert first.read_bytes() == second.read_bytes()


def test_rejects_tampered_runtime_before_packaging(tmp_path: Path) -> None:
    runtime_dir, temporal = _fixture(tmp_path)
    (runtime_dir / "index.faiss").write_bytes(b"tampered")

    try:
        build_runtime_release_bundle(
            runtime_dir=runtime_dir,
            temporal_registry=temporal,
            output_path=tmp_path / "bundle.zip",
        )
    except RuntimeReleaseBundleError as exc:
        assert "index.faiss" in str(exc)
    else:
        raise AssertionError("El runtime alterado debe ser rechazado.")
