from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.services.runtime_inner_integrity_19s_r10 import (
    RuntimeInnerIntegrityError,
    validate_runtime_inner_integrity,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _runtime(tmp_path: Path, *, stale_chunks_sha: bool = False) -> Path:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    chunks = runtime / "chunks.jsonl"
    index = runtime / "index.faiss"
    chunks.write_text('{"id":"1"}\n{"id":"2"}\n', encoding="utf-8")
    index.write_bytes(b"index")
    manifest = {
        "chunk_count": 2,
        "vector_dimension": 384,
        "chunks_bytes": chunks.stat().st_size,
        "index_bytes": index.stat().st_size,
        "chunks_sha256": "0" * 64 if stale_chunks_sha else _sha(chunks),
        "index_sha256": _sha(index),
    }
    (runtime / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    return runtime


def test_accepts_coherent_runtime(tmp_path: Path) -> None:
    result = validate_runtime_inner_integrity(_runtime(tmp_path))
    assert result["chunk_count"] == 2
    assert result["vector_dimension"] == 384


def test_rejects_stale_inner_chunks_digest(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path, stale_chunks_sha=True)
    with pytest.raises(RuntimeInnerIntegrityError, match="chunks.jsonl"):
        validate_runtime_inner_integrity(runtime)


def test_rejects_chunk_count_mismatch(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    manifest_path = runtime / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["chunk_count"] = 3
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RuntimeInnerIntegrityError, match="Cardinalidad"):
        validate_runtime_inner_integrity(runtime)
