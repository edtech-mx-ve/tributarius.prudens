from __future__ import annotations

from typing import cast

import pytest

from app.core.config import Settings
from app.domain.openrouter_llama_runtime import OpenRouterLlamaRuntimeDescriptor
from app.domain.real_llama_runtime import RealLlamaRuntimeDescriptor
from app.services import runtime_factory
from app.services.openrouter_llama_runtime import (
    OpenRouterLlamaRuntimeError,
    build_openrouter_llama_provider,
)
from llm.providers.llama_cpp import LlamaCppProvider
from llm.providers.openrouter import OpenRouterProvider


def _openrouter_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "llm_runtime_provider": "openrouter",
        "require_real_llama": True,
        "openrouter_api_key": "test-secret",
        "openrouter_model": "meta-llama/llama-3.3-70b-instruct:free",
        "openrouter_base_url": "https://openrouter.ai/api/v1",
        "openrouter_timeout_seconds": 180.0,
        "llama_max_tokens": 700,
        "llama_seed": 42,
    }
    values.update(overrides)
    return Settings.model_validate(values)


def test_p2_settings_preserve_local_default_and_allow_openrouter() -> None:
    local = Settings(_env_file=None)
    remote = _openrouter_settings()

    assert local.llm_runtime_provider == "llama_cpp"
    assert remote.llm_runtime_provider == "openrouter"
    assert remote.openrouter_model == "meta-llama/llama-3.3-70b-instruct:free"
    assert remote.openrouter_base_url == "https://openrouter.ai/api/v1"


def test_p2_openrouter_runtime_rejects_missing_key() -> None:
    with pytest.raises(OpenRouterLlamaRuntimeError, match="OPENROUTER_API_KEY"):
        build_openrouter_llama_provider(_openrouter_settings(openrouter_api_key=None))


def test_p2_openrouter_runtime_builds_non_secret_descriptor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeOpenRouterProvider:
        def __init__(self, api_key: str, **kwargs: object) -> None:
            captured["api_key"] = api_key
            captured.update(kwargs)

        @property
        def provider_name(self) -> str:
            return "openrouter"

        @property
        def model_name(self) -> str:
            return "meta-llama/llama-3.3-70b-instruct:free"

    monkeypatch.setattr(
        "app.services.openrouter_llama_runtime.OpenRouterProvider",
        FakeOpenRouterProvider,
    )

    provider, descriptor = build_openrouter_llama_provider(_openrouter_settings())

    assert provider.provider_name == "openrouter"
    assert captured["api_key"] == "test-secret"
    assert descriptor.provider_name == "openrouter"
    assert descriptor.external_llm_api_used is True
    assert descriptor.real_llama_active is True
    assert descriptor.mock_runtime_allowed is False
    assert "test-secret" not in descriptor.model_dump_json()


def test_p2_runtime_factory_selects_openrouter_explicitly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = cast(OpenRouterProvider, object())
    descriptor = OpenRouterLlamaRuntimeDescriptor(
        model_name="meta-llama/llama-3.3-70b-instruct:free",
        base_url="https://openrouter.ai/api/v1",
        max_tokens=700,
        timeout_seconds=180.0,
    )
    observed: list[str] = []

    def build_remote(
        _settings: Settings,
    ) -> tuple[OpenRouterProvider, OpenRouterLlamaRuntimeDescriptor]:
        observed.append("openrouter")
        return provider, descriptor

    def fail_local(_settings: Settings) -> tuple[LlamaCppProvider, object]:
        raise AssertionError("No debe construir llama.cpp en modo openrouter.")

    monkeypatch.setattr(runtime_factory, "build_openrouter_llama_provider", build_remote)
    monkeypatch.setattr(runtime_factory, "build_real_llama_provider", fail_local)

    selected_provider, selected_descriptor = runtime_factory._build_runtime_llama_provider(
        _openrouter_settings()
    )

    assert selected_provider is provider
    assert selected_descriptor is descriptor
    assert observed == ["openrouter"]


def test_p2_runtime_factory_preserves_llama_cpp_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = cast(LlamaCppProvider, object())
    descriptor = RealLlamaRuntimeDescriptor(
        model_name="fixture",
        model_path="model.gguf",
        model_sha256="0" * 64,
        n_ctx=2048,
        max_tokens=700,
        n_threads=1,
        n_batch=64,
    )
    observed: list[str] = []

    def build_local(
        _settings: Settings,
    ) -> tuple[LlamaCppProvider, RealLlamaRuntimeDescriptor]:
        observed.append("llama_cpp")
        return provider, descriptor

    def fail_remote(
        _settings: Settings,
    ) -> tuple[OpenRouterProvider, OpenRouterLlamaRuntimeDescriptor]:
        raise AssertionError("No debe construir OpenRouter en modo llama_cpp.")

    monkeypatch.setattr(runtime_factory, "build_real_llama_provider", build_local)
    monkeypatch.setattr(runtime_factory, "build_openrouter_llama_provider", fail_remote)

    selected_provider, selected_descriptor = runtime_factory._build_runtime_llama_provider(
        Settings(_env_file=None)
    )

    assert selected_provider is provider
    assert selected_descriptor is descriptor
    assert observed == ["llama_cpp"]
