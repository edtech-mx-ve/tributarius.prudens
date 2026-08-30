from __future__ import annotations

import pytest

from app.services.runtime_factory import RuntimeBuildError, runtime_backend_name


def test_runtime_backend_defaults_to_semantic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RAG_RUNTIME_BACKEND", raising=False)
    assert runtime_backend_name() == "semantic"


def test_runtime_backend_accepts_lexical_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAG_RUNTIME_BACKEND", "lexical_cpu")
    assert runtime_backend_name() == "lexical_cpu"


def test_runtime_backend_rejects_unknown_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAG_RUNTIME_BACKEND", "gpu_magic")
    with pytest.raises(RuntimeBuildError, match="RAG_RUNTIME_BACKEND inválido"):
        runtime_backend_name()
