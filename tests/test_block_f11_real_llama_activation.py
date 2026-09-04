from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.config import Settings
from app.services.hybrid_contract_baseline import audit_current_hybrid_contracts
from app.services.real_llama_runtime import (
    RealLlamaRuntimeError,
    build_real_llama_provider,
    validate_real_llama_model,
)
from app.web.presenter import present_legal_decision
from llm.providers.llama_cpp import LlamaCppProvider
from scripts.bootstrap_llama_model_f11 import bootstrap_llama_model
from scripts.validate_deployment import validate_render_blueprint
from tests.test_block_f10_hybrid_llama_runtime import (
    ScriptedStructuredProvider,
    _request,
    _runtime,
)

MODEL_SHA = "3f5a22426976ab26cfe84dba63c1d08391717abb1af893e10f1b2968d862dcc1"


def _settings_for_model(path: Path, sha256: str) -> Settings:
    return Settings(
        _env_file=None,
        llm_runtime_provider="llama_cpp",
        require_real_llama=True,
        llama_model_path=str(path),
        llama_model_sha256=sha256,
        llama_n_ctx=2048,
        llama_max_tokens=256,
        llama_n_threads=1,
        llama_n_batch=64,
    )


def test_f11_settings_default_to_real_llama_not_mock() -> None:
    settings = Settings(_env_file=None)

    assert settings.llm_runtime_provider == "llama_cpp"
    assert settings.require_real_llama is True
    assert settings.llama_model_path.endswith(".gguf")
    assert settings.llama_model_sha256 == MODEL_SHA


def test_f11_validates_real_gguf_integrity(tmp_path: Path) -> None:
    model = tmp_path / "model.gguf"
    model.write_bytes(b"real-llama-fixture")
    expected = hashlib.sha256(model.read_bytes()).hexdigest()

    path, actual = validate_real_llama_model(_settings_for_model(model, expected))

    assert path == model.resolve()
    assert actual == expected


def test_f11_rejects_wrong_model_hash(tmp_path: Path) -> None:
    model = tmp_path / "model.gguf"
    model.write_bytes(b"tampered")

    with pytest.raises(RealLlamaRuntimeError, match="SHA-256"):
        validate_real_llama_model(_settings_for_model(model, "0" * 64))


def test_f11_builds_descriptor_from_real_provider_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = tmp_path / "model.gguf"
    model.write_bytes(b"real-llama-fixture")
    expected = hashlib.sha256(model.read_bytes()).hexdigest()
    captured: dict[str, Any] = {}

    class FakeLoadedLlamaCppProvider:
        def __init__(self, model_path: Path, **kwargs: object) -> None:
            captured["path"] = model_path
            captured.update(kwargs)

        @property
        def provider_name(self) -> str:
            return "llama-cpp-python"

        @property
        def model_name(self) -> str:
            return "model"

    monkeypatch.setattr(
        "app.services.real_llama_runtime.LlamaCppProvider",
        FakeLoadedLlamaCppProvider,
    )

    provider, descriptor = build_real_llama_provider(
        _settings_for_model(model, expected)
    )

    assert provider.provider_name == "llama-cpp-python"
    assert captured["path"] == model.resolve()
    assert captured["n_ctx"] == 2048
    assert captured["n_threads"] == 1
    assert captured["n_batch"] == 64
    assert descriptor.real_llama_active is True
    assert descriptor.h1_uses_real_llama is True
    assert descriptor.h2_uses_real_llama is True
    assert descriptor.semantic_verifier_uses_real_llama is True
    assert descriptor.explanation_uses_real_llama is True
    assert descriptor.external_llm_api_used is False
    assert descriptor.mock_runtime_allowed is False


def test_f11_llama_cpp_provider_uses_cpu_bounded_backend(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = tmp_path / "model.gguf"
    model.write_bytes(b"fixture")
    init_kwargs: dict[str, object] = {}

    class FakeBackend:
        def create_chat_completion(self, **kwargs: object) -> object:
            del kwargs
            return {"choices": [{"message": {"content": '{"ok": true}'}}]}

    def factory(**kwargs: object) -> FakeBackend:
        init_kwargs.update(kwargs)
        return FakeBackend()

    monkeypatch.setattr(
        "llm.providers.llama_cpp.importlib.import_module",
        lambda name: SimpleNamespace(Llama=factory) if name == "llama_cpp" else None,
    )

    provider = LlamaCppProvider(
        model,
        n_ctx=2048,
        max_tokens=128,
        n_threads=1,
        n_batch=64,
    )
    raw = provider.generate_messages_json(
        [{"role": "user", "content": "{}"}],
        response_schema={"type": "object"},
    )

    assert json.loads(raw) == {"ok": True}
    assert init_kwargs["n_gpu_layers"] == 0
    assert init_kwargs["n_threads"] == 1
    assert init_kwargs["n_threads_batch"] == 1
    assert init_kwargs["n_batch"] == 64
    assert init_kwargs["use_mmap"] is True
    assert init_kwargs["use_mlock"] is False


def test_f11_runtime_factory_has_no_mock_production_path() -> None:
    source = Path("app/services/runtime_factory.py").read_text(encoding="utf-8")

    assert "MockLLMProvider" not in source
    assert "build_real_llama_provider(settings)" in source
    assert "build_hybrid_llama_service_bundle(llama_provider)" in source
    assert "LlamaRAGService(llama_provider)" in source
    assert "hybrid_h1_service=llama_services.h1" in source
    assert "provider_is_test_double=False" in source
    assert "hybrid_llama_runtime=hybrid_llama_runtime" in source


def test_f11_render_blueprint_bootstraps_real_model_and_memory_profile() -> None:
    checks = set(validate_render_blueprint(Path("render.yaml")))

    assert "plan=1c-2g" in checks
    assert "build-installs-llama-cpp-cpu-wheel" in checks
    assert "build-installs-package-with-llama" in checks
    assert "build-bootstraps-real-llama" in checks
    assert "real-llama-provider" in checks
    assert "real-llama-required" in checks
    assert "llama-model-sha-pinned" in checks
    assert "llama-model-url-revision-pinned" in checks


def test_f11_llama_dependency_is_pinned_for_reproducible_cpu_wheel() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert '"llama-cpp-python==0.3.35"' in pyproject
    assert '"huggingface-hub>=1.3,<2.0"' in pyproject



def test_f11_huggingface_bootstrap_uses_hub_xet_aware_download(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"GGUF-hugging-face-xet-aware-fixture"
    expected = hashlib.sha256(payload).hexdigest()
    cached = tmp_path / "cache.gguf"
    cached.write_bytes(payload)
    captured: dict[str, str] = {}

    def fake_hf_hub_download(
        *,
        repo_id: str,
        filename: str,
        revision: str,
    ) -> str:
        captured["repo_id"] = repo_id
        captured["filename"] = filename
        captured["revision"] = revision
        return str(cached)

    monkeypatch.setattr(
        "scripts.bootstrap_llama_model_f11.hf_hub_download",
        fake_hf_hub_download,
    )

    destination = tmp_path / "model.gguf"
    source = (
        "https://huggingface.co/unsloth/Llama-3.2-1B-Instruct-GGUF/"
        "resolve/b69aef112e9f895e6f98d7ae0949f72ff09aa401/Llama-3.2-1B-Instruct-Q4_K_M.gguf"
    )
    path, actual, size = bootstrap_llama_model(
        source=source,
        expected_sha256=expected,
        destination=destination,
        max_bytes=1024,
    )

    assert captured == {
        "repo_id": "unsloth/Llama-3.2-1B-Instruct-GGUF",
        "filename": "Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        "revision": "b69aef112e9f895e6f98d7ae0949f72ff09aa401",
    }
    assert path == destination.resolve()
    assert actual == expected
    assert size == len(payload)
    assert destination.read_bytes() == payload


def test_f11_model_bootstrap_verifies_download_before_promotion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"gguf-real-model-fixture"
    expected = hashlib.sha256(payload).hexdigest()

    class FakeResponse:
        headers = {"Content-Length": str(len(payload))}

        def __enter__(self) -> FakeResponse:
            self._sent = False
            return self

        def __exit__(self, *args: object) -> None:
            del args

        def read(self, size: int) -> bytes:
            del size
            if self._sent:
                return b""
            self._sent = True
            return payload

    monkeypatch.setattr(
        "scripts.bootstrap_llama_model_f11.urllib.request.urlopen",
        lambda request, timeout: FakeResponse(),
    )
    destination = tmp_path / "model.gguf"

    path, actual, size = bootstrap_llama_model(
        source="https://example.invalid/model.gguf",
        expected_sha256=expected,
        destination=destination,
        max_bytes=1024,
    )

    assert path == destination.resolve()
    assert actual == expected
    assert size == len(payload)
    assert destination.read_bytes() == payload
    assert not destination.with_suffix(".gguf.part").exists()


def test_f11_web_presenter_accepts_hybrid_f9_decision() -> None:
    result = _runtime(ScriptedStructuredProvider([])).run(_request())

    payload = present_legal_decision(result.decision)

    assert payload["schema_version"] == "1.1"
    assert payload["hybrid_analysis_consumed"] is True
    assert payload["integrity_sha256"]


def test_f11_preserves_f1_public_contracts_while_authorizing_real_runtime() -> None:
    audit = audit_current_hybrid_contracts()

    assert audit.all_contracts_preserved is True
    assert all(item.preserved for item in audit.runtime_checks)
    assert any(
        "F.11 activó Llama real" in item.detail
        for item in audit.runtime_checks
    )
