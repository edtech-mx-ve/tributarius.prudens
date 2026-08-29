from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from app.services import public_release_cold_start_19i18n as cold_start
from app.services.runtime_public_release_installer_19s_r4 import (
    RuntimeReleaseInstallError,
    install_public_runtime_release,
)


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _candidate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    staging = tmp_path / "staging"
    runtime = staging / "runtime"
    runtime.mkdir(parents=True)
    (runtime / "index.faiss").write_bytes(b"index")
    (runtime / "chunks.jsonl").write_bytes(b"{}\n")
    (runtime / "manifest.json").write_bytes(b"{}\n")

    metadata = {
        "candidate_only": True,
        "canonical_sha256": cold_start.EXPECTED_CANONICAL_SHA256,
        "parent_count": cold_start.EXPECTED_PARENT_COUNT,
        "normative_document_count": 14,
        "benchmark_passed": True,
        "blocked_content_absent": True,
        "provenance_complete": True,
        "temporal_fail_closed_complete": True,
        "temporal_validity_complete": False,
        "redistribution_human_review_required": True,
        "publication_legal_acceptance": False,
        "public_release_allowed": False,
        "git_push_allowed": False,
        "github_release_allowed": False,
        "render_deploy_allowed": False,
        "automatic_publication_performed": False,
    }
    (staging / "release_metadata.json").write_bytes(_json_bytes(metadata))

    files: list[dict[str, object]] = []
    for path in sorted(staging.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(staging).as_posix()
        payload = path.read_bytes()
        files.append(
            {
                "path": rel,
                "size": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    manifest = {
        "candidate_only": True,
        "canonical_sha256": cold_start.EXPECTED_CANONICAL_SHA256,
        "files": files,
    }
    (staging / "release_manifest.json").write_bytes(_json_bytes(manifest))

    bundle = tmp_path / "candidate.zip"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(staging).as_posix())

    digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
    monkeypatch.setattr(cold_start, "EXPECTED_CANDIDATE_SHA256", digest)
    return bundle, digest


def _project_root(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    temporal = root / "knowledge/temporal/temporal_provenance_registry.json"
    temporal.parent.mkdir(parents=True)
    temporal.write_text("{}\n", encoding="utf-8")
    return root


def test_installs_public_candidate_into_runtime_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle, digest = _candidate(tmp_path, monkeypatch)
    root = _project_root(tmp_path)

    result = install_public_runtime_release(
        source=str(bundle),
        expected_sha256=digest,
        project_root=root,
    )

    runtime = root / "deployment/runtime_artifacts_semantic_v2"
    assert (runtime / "index.faiss").read_bytes() == b"index"
    assert (runtime / "chunks.jsonl").read_bytes() == b"{}\n"
    assert (runtime / "manifest.json").read_bytes() == b"{}\n"
    assert result.bundle_sha256 == digest
    assert len(result.installed_files) == 4


def test_requires_tracked_temporal_registry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle, digest = _candidate(tmp_path, monkeypatch)

    with pytest.raises(
        RuntimeReleaseInstallError,
        match="Registro temporal versionado ausente",
    ):
        install_public_runtime_release(
            source=str(bundle),
            expected_sha256=digest,
            project_root=tmp_path / "project",
        )


def test_rejects_outer_sha_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle, _digest = _candidate(tmp_path, monkeypatch)
    root = _project_root(tmp_path)

    with pytest.raises(RuntimeReleaseInstallError, match="SHA-256"):
        install_public_runtime_release(
            source=str(bundle),
            expected_sha256="0" * 64,
            project_root=root,
        )


def test_rejects_extra_public_bundle_member(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle, _digest = _candidate(tmp_path, monkeypatch)
    with zipfile.ZipFile(bundle, "a", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("runtime/extra.json", b"{}")
    digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
    monkeypatch.setattr(cold_start, "EXPECTED_CANDIDATE_SHA256", digest)
    root = _project_root(tmp_path)

    with pytest.raises(
        RuntimeReleaseInstallError,
        match="Contenido público inesperado",
    ):
        install_public_runtime_release(
            source=str(bundle),
            expected_sha256=digest,
            project_root=root,
        )
