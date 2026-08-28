from pathlib import Path

from app.core.config import Settings
from app.domain.deployment import ReadinessState
from app.services import runtime_readiness


def settings(tmp_path: Path, *, require_rag_artifacts: bool) -> Settings:
    return Settings(
        _env_file=None,
        rag_artifact_dir=str(tmp_path / "runtime"),
        require_rag_artifacts=require_rag_artifacts,
    )


def test_readiness_is_degraded_when_optional_rag_artifacts_are_absent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        runtime_readiness,
        "_database_capability",
        lambda: runtime_readiness.RuntimeCapability(
            name="database",
            available=True,
            detail="ok",
        ),
    )
    report = runtime_readiness.build_readiness_report(
        settings(tmp_path, require_rag_artifacts=False)
    )
    assert report.state == ReadinessState.DEGRADED


def test_readiness_fails_when_required_rag_artifacts_are_absent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        runtime_readiness,
        "_database_capability",
        lambda: runtime_readiness.RuntimeCapability(
            name="database",
            available=True,
            detail="ok",
        ),
    )
    report = runtime_readiness.build_readiness_report(
        settings(tmp_path, require_rag_artifacts=True)
    )
    assert report.state == ReadinessState.NOT_READY


def test_readiness_is_ready_with_complete_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    directory = tmp_path / "runtime"
    directory.mkdir()
    for filename in ("index.faiss", "chunks.jsonl", "manifest.json"):
        (directory / filename).write_text("fixture", encoding="utf-8")

    monkeypatch.setattr(
        runtime_readiness,
        "_database_capability",
        lambda: runtime_readiness.RuntimeCapability(
            name="database",
            available=True,
            detail="ok",
        ),
    )
    report = runtime_readiness.build_readiness_report(
        settings(tmp_path, require_rag_artifacts=True)
    )
    assert report.state == ReadinessState.READY
