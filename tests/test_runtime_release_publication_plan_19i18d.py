from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from app.services.runtime_release_publication_plan import (
    RuntimeReleasePublicationPlanError,
    build_publication_plan,
)


def _bundle(tmp_path: Path) -> tuple[Path, str]:
    path = tmp_path / "runtime.zip"
    manifest = {
        "schema_version": "1.0",
        "artifact": "tributarius-prudens-runtime-semantic-v2",
        "runtime_chunk_count": 29326,
        "runtime_vector_dimension": 384,
        "runtime_model_name": (
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        ),
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "release_manifest.json",
            json.dumps(manifest).encode("utf-8"),
        )
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return path, digest


def test_builds_local_publication_plan(tmp_path: Path) -> None:
    bundle, digest = _bundle(tmp_path)

    plan = build_publication_plan(
        bundle_path=bundle,
        expected_sha256=digest,
        repository="owner/repo",
        output_dir=tmp_path / "out",
    )

    assert plan.asset_sha256 == digest
    assert plan.asset_url == (
        "https://github.com/owner/repo/releases/download/"
        "runtime-semantic-v2-19i18/"
        "tributarius-prudens-runtime-semantic-v2.zip"
    )
    payload = json.loads(Path(plan.plan_path).read_text(encoding="utf-8"))
    assert payload["publication_status"] == "local_plan_only"
    assert "gh release create" in payload["publish_command_template"]


def test_rejects_wrong_sha(tmp_path: Path) -> None:
    bundle, _ = _bundle(tmp_path)

    with pytest.raises(
        RuntimeReleasePublicationPlanError,
        match="SHA-256",
    ):
        build_publication_plan(
            bundle_path=bundle,
            expected_sha256="0" * 64,
            repository="owner/repo",
            output_dir=tmp_path / "out",
        )


def test_rejects_invalid_repository(tmp_path: Path) -> None:
    bundle, digest = _bundle(tmp_path)

    with pytest.raises(
        RuntimeReleasePublicationPlanError,
        match="owner/repo",
    ):
        build_publication_plan(
            bundle_path=bundle,
            expected_sha256=digest,
            repository="not-a-repository",
            output_dir=tmp_path / "out",
        )


def test_rejects_wrong_artifact_kind(tmp_path: Path) -> None:
    bundle = tmp_path / "wrong.zip"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "release_manifest.json",
            json.dumps({"artifact": "other"}).encode("utf-8"),
        )
    digest = hashlib.sha256(bundle.read_bytes()).hexdigest()

    with pytest.raises(
        RuntimeReleasePublicationPlanError,
        match="runtime semántico v2",
    ):
        build_publication_plan(
            bundle_path=bundle,
            expected_sha256=digest,
            repository="owner/repo",
            output_dir=tmp_path / "out",
        )
