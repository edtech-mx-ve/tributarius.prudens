from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.services.public_release_candidate_19i18m import (
    ReleaseCandidateError,
    refresh_runtime_inner_manifest,
)


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_refresh_updates_stale_chunks_digest_before_outer_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    chunks = runtime / "chunks.jsonl"
    index = runtime / "index.faiss"
    chunks.write_bytes(b'{"text":"sanitized"}\n')
    index.write_bytes(b"faiss")
    _write_json(
        runtime / "manifest.json",
        {
            "chunk_count": 1,
            "chunks_bytes": 1,
            "chunks_sha256": "0" * 64,
            "index_bytes": len(b"faiss"),
            "index_sha256": hashlib.sha256(b"faiss").hexdigest(),
            "vector_dimension": 384,
        },
    )

    monkeypatch.setattr(
        "app.services.public_release_candidate_19i18m."
        "validate_runtime_inner_integrity",
        lambda path: {
            "chunks_sha256": hashlib.sha256(chunks.read_bytes()).hexdigest(),
            "chunks_bytes": chunks.stat().st_size,
        },
    )

    result = refresh_runtime_inner_manifest(runtime)
    manifest = json.loads((runtime / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["chunks_sha256"] == hashlib.sha256(chunks.read_bytes()).hexdigest()
    assert manifest["chunks_bytes"] == chunks.stat().st_size
    assert result["chunks_sha256"] == manifest["chunks_sha256"]


def test_refresh_is_fail_closed_when_structural_integrity_rejects(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "chunks.jsonl").write_bytes(b"{}\n")
    (runtime / "index.faiss").write_bytes(b"faiss")
    _write_json(runtime / "manifest.json", {"chunk_count": 1})

    from app.services.runtime_inner_integrity_19s_r10 import RuntimeInnerIntegrityError

    def reject(_: Path) -> dict[str, int | str]:
        raise RuntimeInnerIntegrityError("FAISS/chunks desalineados")

    monkeypatch.setattr(
        "app.services.public_release_candidate_19i18m."
        "validate_runtime_inner_integrity",
        reject,
    )

    with pytest.raises(ReleaseCandidateError, match="FAISS/chunks desalineados"):
        refresh_runtime_inner_manifest(runtime)
