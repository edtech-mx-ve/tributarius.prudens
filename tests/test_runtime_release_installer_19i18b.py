from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from app.services.runtime_release_installer import (
    RuntimeReleaseInstallError,
    install_runtime_release,
)


def _make_bundle(tmp_path: Path) -> tuple[Path, str]:
    payloads = {
        "deployment/runtime_artifacts_semantic_v2/index.faiss": b"index",
        "deployment/runtime_artifacts_semantic_v2/chunks.jsonl": b"{}\n",
        "deployment/runtime_artifacts_semantic_v2/manifest.json": b"{}\n",
        "knowledge/temporal/temporal_provenance_registry.json": b"{}\n",
    }
    release_manifest = {
        "schema_version": "1.0",
        "artifact": "fixture",
        "files": {
            name: {
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size_bytes": len(payload),
            }
            for name, payload in payloads.items()
        },
    }
    bundle = tmp_path / "bundle.zip"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in payloads.items():
            archive.writestr(name, payload)
        archive.writestr(
            "release_manifest.json",
            json.dumps(release_manifest).encode("utf-8"),
        )
    return bundle, hashlib.sha256(bundle.read_bytes()).hexdigest()


def test_installs_verified_local_bundle(tmp_path: Path) -> None:
    bundle, digest = _make_bundle(tmp_path)
    root = tmp_path / "project"

    result = install_runtime_release(
        source=str(bundle),
        expected_sha256=digest,
        project_root=root,
    )

    assert result.bundle_sha256 == digest
    assert (
        root / "deployment/runtime_artifacts_semantic_v2/index.faiss"
    ).read_bytes() == b"index"
    assert (
        root / "knowledge/temporal/temporal_provenance_registry.json"
    ).read_bytes() == b"{}\n"


def test_rejects_wrong_bundle_sha(tmp_path: Path) -> None:
    bundle, _ = _make_bundle(tmp_path)

    with pytest.raises(
        RuntimeReleaseInstallError,
        match="SHA-256",
    ):
        install_runtime_release(
            source=str(bundle),
            expected_sha256="0" * 64,
            project_root=tmp_path / "project",
        )


def test_rejects_non_https_url(tmp_path: Path) -> None:
    with pytest.raises(
        RuntimeReleaseInstallError,
        match="No existe bundle local",
    ):
        install_runtime_release(
            source="http://example.invalid/runtime.zip",
            expected_sha256="0" * 64,
            project_root=tmp_path / "project",
        )


def test_rejects_unexpected_archive_member(tmp_path: Path) -> None:
    bundle, _ = _make_bundle(tmp_path)
    modified = tmp_path / "modified.zip"
    modified.write_bytes(bundle.read_bytes())
    with zipfile.ZipFile(modified, "a", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("../escape.txt", b"bad")
    digest = hashlib.sha256(modified.read_bytes()).hexdigest()

    with pytest.raises(
        RuntimeReleaseInstallError,
        match="Ruta ZIP insegura",
    ):
        install_runtime_release(
            source=str(modified),
            expected_sha256=digest,
            project_root=tmp_path / "project",
        )
