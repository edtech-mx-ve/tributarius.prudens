from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from app.services.public_release_integrity_19s_r10 import (
    PublicReleaseIntegrityError,
    repair_candidate,
    validate_candidate,
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _candidate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    import app.services.public_release_integrity_19s_r10 as module

    chunks = b'{"id":"a"}\n{"id":"b"}\n'
    index = b"fake-index"
    manifest = {
        "chunk_count": 2,
        "vector_dimension": 384,
        "chunks_sha256": "0" * 64,
        "chunks_bytes": len(chunks),
        "index_sha256": _sha(index),
        "index_bytes": len(index),
    }
    metadata = {"candidate_only": True}
    members = {
        "runtime/chunks.jsonl": chunks,
        "runtime/index.faiss": index,
        "runtime/manifest.json": (
            json.dumps(manifest, sort_keys=True, indent=2) + "\n"
        ).encode(),
        "release_metadata.json": (
            json.dumps(metadata, sort_keys=True, indent=2) + "\n"
        ).encode(),
    }
    release = {
        "candidate_only": True,
        "files": [
            {"path": name, "size": len(data), "sha256": _sha(data)}
            for name, data in sorted(members.items())
        ],
    }
    members["release_manifest.json"] = (
        json.dumps(release, sort_keys=True, indent=2) + "\n"
    ).encode()

    path = tmp_path / "source.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)

    monkeypatch.setattr(module, "_faiss_shape", lambda _: (2, 384))
    return path


def test_original_candidate_with_stale_chunks_sha_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _candidate(tmp_path, monkeypatch)
    with pytest.raises(PublicReleaseIntegrityError, match="SHA-256 de chunks"):
        validate_candidate(source)


def test_repair_updates_inner_and_outer_integrity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _candidate(tmp_path, monkeypatch)
    output = tmp_path / "repaired.zip"

    summary = repair_candidate(source, output)

    assert summary.chunk_count == 2
    assert summary.index_ntotal == 2
    assert summary.vector_dimension == 384
    with zipfile.ZipFile(output) as archive:
        chunks = archive.read("runtime/chunks.jsonl")
        manifest = json.loads(archive.read("runtime/manifest.json"))
        release = json.loads(archive.read("release_manifest.json"))
        assert manifest["chunks_sha256"] == _sha(chunks)
        assert manifest["chunks_bytes"] == len(chunks)
        outer = {item["path"]: item for item in release["files"]}
        runtime_manifest = archive.read("runtime/manifest.json")
        assert outer["runtime/manifest.json"]["sha256"] == _sha(runtime_manifest)


def test_repair_refuses_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _candidate(tmp_path, monkeypatch)
    output = tmp_path / "exists.zip"
    output.write_bytes(b"x")
    with pytest.raises(PublicReleaseIntegrityError, match="ya existe"):
        repair_candidate(source, output)
