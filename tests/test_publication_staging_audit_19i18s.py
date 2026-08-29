from __future__ import annotations

from app.services.publication_staging_audit_19i18s import (
    PUBLIC_RUNTIME_SHA256,
    find_forbidden_staged_paths,
    render_uses_public_runtime_sha,
)


def test_forbidden_generated_runtime_is_rejected() -> None:
    rejected = find_forbidden_staged_paths(
        ["deployment/runtime_artifacts_semantic_v2/index.faiss"]
    )
    assert rejected == ("deployment/runtime_artifacts_semantic_v2/index.faiss",)


def test_forbidden_reports_are_rejected() -> None:
    rejected = find_forbidden_staged_paths(
        ["reports/sprint19I18R/human_release_gate_acceptance.json"]
    )
    assert rejected


def test_private_env_is_rejected() -> None:
    assert find_forbidden_staged_paths([".env"]) == (".env",)


def test_safe_source_paths_are_allowed() -> None:
    assert find_forbidden_staged_paths(
        [
            "app/services/runtime_release_installer.py",
            "tests/test_runtime_release_installer_19i18b.py",
            "docs/sprint_19I_18R.md",
            "knowledge/temporal/temporal_provenance_registry.json",
            "evidence/publication/human_release_decision_19i18r.json",
        ]
    ) == ()


def test_render_accepts_exact_public_runtime_sha() -> None:
    payload = f"RUNTIME_RELEASE_SHA256: {PUBLIC_RUNTIME_SHA256}"
    assert render_uses_public_runtime_sha(payload)


def test_render_rejects_old_runtime_sha() -> None:
    old = "687c9f6bba0b166b3728ce387d560644523d260cde1f7a298655954e490cbda4c"
    assert not render_uses_public_runtime_sha(f"RUNTIME_RELEASE_SHA256: {old}")
