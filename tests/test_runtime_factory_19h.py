from pathlib import Path

import pytest

from app.core.config import Settings
from app.services.runtime_factory import RuntimeBuildError, validate_runtime_assets


def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        rag_artifact_dir=str(tmp_path / "runtime"),
        legal_retrieval_policy_path=str(tmp_path / "policy.json"),
        runtime_rule_set_path=str(tmp_path / "rules.json"),
    )


def test_runtime_assets_fail_closed_when_rag_is_missing(tmp_path: Path) -> None:
    with pytest.raises(RuntimeBuildError, match="Faltan artefactos RAG"):
        validate_runtime_assets(settings(tmp_path))


def test_runtime_assets_validate_manifest_and_support_files(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "index.faiss").write_bytes(b"fake")
    (runtime / "chunks.jsonl").write_text("{}\n", encoding="utf-8")
    (runtime / "manifest.json").write_text(
        """
        {
          "created_at_utc": "2026-08-29T00:00:00Z",
          "model_name": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
          "vector_dimension": 384,
          "chunk_count": 1,
          "source_chunk_files": ["fixture"],
          "index_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "chunks_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        }
        """,
        encoding="utf-8",
    )
    (tmp_path / "policy.json").write_text("{}", encoding="utf-8")
    (tmp_path / "rules.json").write_text("{}", encoding="utf-8")

    artifact_dir, manifest = validate_runtime_assets(settings(tmp_path))

    assert artifact_dir == runtime.resolve()
    assert manifest.vector_dimension == 384
