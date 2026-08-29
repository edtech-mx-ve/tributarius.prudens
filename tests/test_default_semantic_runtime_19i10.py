from __future__ import annotations

from app.core.config import Settings


def test_default_rag_artifact_dir_is_semantic_v2() -> None:
    settings = Settings(_env_file=None)
    assert (
        settings.rag_artifact_dir
        == "deployment/runtime_artifacts_semantic_v2"
    )
