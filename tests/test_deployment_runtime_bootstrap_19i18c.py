from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.validate_deployment import (
    DeploymentValidationError,
    validate_render_blueprint,
)


def test_repository_render_blueprint_uses_verified_runtime_bootstrap() -> None:
    checks = validate_render_blueprint(Path("render.yaml"))

    assert "build-bootstraps-runtime" in checks
    assert "release-url-external" in checks
    assert "release-sha-pinned" in checks
    assert "semantic-v2-runtime" in checks
    assert "temporal-registry-required" in checks


def test_validator_rejects_missing_bootstrap_command(tmp_path: Path) -> None:
    payload = yaml.safe_load(Path("render.yaml").read_text(encoding="utf-8"))
    payload["services"][0]["buildCommand"] = "python -m pip install -e ."
    candidate = tmp_path / "render.yaml"
    candidate.write_text(yaml.safe_dump(payload), encoding="utf-8")

    with pytest.raises(
        DeploymentValidationError,
        match="build-bootstraps-runtime",
    ):
        validate_render_blueprint(candidate)


def test_validator_rejects_unpinned_release_sha(tmp_path: Path) -> None:
    payload = yaml.safe_load(Path("render.yaml").read_text(encoding="utf-8"))
    for item in payload["services"][0]["envVars"]:
        if item.get("key") == "RUNTIME_RELEASE_SHA256":
            item["value"] = "0" * 64
    candidate = tmp_path / "render.yaml"
    candidate.write_text(yaml.safe_dump(payload), encoding="utf-8")

    with pytest.raises(
        DeploymentValidationError,
        match="release-sha-pinned",
    ):
        validate_render_blueprint(candidate)


def test_validator_requires_release_url_as_external_env(tmp_path: Path) -> None:
    payload = yaml.safe_load(Path("render.yaml").read_text(encoding="utf-8"))
    for item in payload["services"][0]["envVars"]:
        if item.get("key") == "RUNTIME_RELEASE_URL":
            item.pop("sync", None)
            item["value"] = "https://example.invalid/runtime.zip"
    candidate = tmp_path / "render.yaml"
    candidate.write_text(yaml.safe_dump(payload), encoding="utf-8")

    with pytest.raises(
        DeploymentValidationError,
        match="release-url-external",
    ):
        validate_render_blueprint(candidate)
