from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import faiss
import numpy as np
import pytest

import app.services.public_release_deployment_dependency_19i18o as o


class FakeModel:
    def __init__(self, vector: np.ndarray) -> None:
        self._vector = vector

    def encode(self, *_args: Any, **_kwargs: Any) -> np.ndarray:
        return self._vector


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _runtime(tmp_path: Path) -> Path:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    _write_json(
        runtime / "manifest.json",
        {"embedding_model": "sentence-transformers/example-model"},
    )
    chunks = [
        {
            "chunk_id": "a",
            "metadata": {"document_id": "cff"},
            "text": "Código Fiscal",
        },
        {
            "chunk_id": "b",
            "metadata": {"document_id": "lisr"},
            "text": "ISR",
        },
    ]
    (runtime / "chunks.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in chunks),
        encoding="utf-8",
    )
    index = faiss.IndexFlatIP(3)
    index.add(
        np.asarray(
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            dtype="float32",
        )
    )
    faiss.write_index(index, str(runtime / "index.faiss"))
    return runtime


def test_model_id_is_resolved_from_runtime(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    assert (
        o.resolve_embedding_model_id(runtime)
        == "sentence-transformers/example-model"
    )


def test_ambiguous_model_id_fails_closed(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    _write_json(
        runtime / "other.json",
        {"model_name": "sentence-transformers/other-model"},
    )
    with pytest.raises(o.DeploymentDependencyError, match="único modelo"):
        o.resolve_embedding_model_id(runtime)


def test_semantic_query_probe_matches_dimension(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    model = FakeModel(
        np.asarray([[1.0, 0.0, 0.0]], dtype="float32")
    )
    probe = o.semantic_query_probe(
        runtime_dir=runtime,
        model=model,  # type: ignore[arg-type]
        model_id="sentence-transformers/example-model",
        query="obligaciones fiscales",
    )
    assert probe.embedding_dimension == 3
    assert probe.faiss_dimension == 3
    assert probe.faiss_ntotal == 2
    assert probe.top_document_ids[0] == "cff"


def test_semantic_query_probe_rejects_dimension_mismatch(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    model = FakeModel(
        np.asarray([[1.0, 0.0, 0.0, 0.0]], dtype="float32")
    )
    with pytest.raises(o.DeploymentDependencyError, match="incompatible"):
        o.semantic_query_probe(
            runtime_dir=runtime,
            model=model,  # type: ignore[arg-type]
            model_id="sentence-transformers/example-model",
            query="x",
        )


def test_19n_gate_requires_cold_start_acceptance(tmp_path: Path) -> None:
    report = tmp_path / "19n.json"
    _write_json(
        report,
        {
            "candidate_zip_sha256": o.EXPECTED_CANDIDATE_SHA256,
            "canonical_sha256": o.EXPECTED_CANONICAL_SHA256,
            "manifest_integrity_passed": True,
            "zip_path_safety_passed": True,
            "runtime_loaded_from_extracted_candidate_only": True,
            "source_runtime_path_not_used": True,
            "blocked_document_identity_absent": True,
            "cold_start_acceptance": False,
            "embedding_model_bundled": False,
            "embedding_model_external_dependency": True,
            "semantic_query_embedding_cold_start_proven": False,
            "deployment_sufficiency_acceptance": False,
            "public_release_allowed": False,
            "git_push_allowed": False,
            "github_release_allowed": False,
            "render_deploy_allowed": False,
        },
    )
    with pytest.raises(o.DeploymentDependencyError, match="precondiciones"):
        o.validate_upstream_19n(report)


def test_existing_cache_is_not_overwritten(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    with pytest.raises(o.DeploymentDependencyError, match="Cache 19O ya existe"):
        o.prefetch_and_verify_offline(
            "sentence-transformers/example-model",
            cache,
        )
