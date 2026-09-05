from __future__ import annotations

from typing import cast

import pytest

from app.core.config import Settings
from app.domain.cloudflare_workers_ai_runtime import CloudflareWorkersAIRuntimeDescriptor
from app.services import runtime_factory
from app.services.cloudflare_workers_ai_runtime import (
    CloudflareWorkersAIRuntimeError,
    build_cloudflare_workers_ai_provider,
)
from llm.providers.cloudflare_workers_ai import CloudflareWorkersAIProvider
from llm.providers.llama_cpp import LlamaCppProvider
from llm.providers.openrouter import OpenRouterProvider

_ACCOUNT_ID = "0123456789abcdef0123456789abcdef"


def _cloudflare_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "llm_runtime_provider": "cloudflare_workers_ai",
        "require_real_llama": True,
        "cloudflare_account_id": _ACCOUNT_ID,
        "cloudflare_auth_token": "test-secret",
        "cloudflare_workers_ai_model": "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
        "cloudflare_workers_ai_base_url": "https://api.cloudflare.com/client/v4",
        "cloudflare_workers_ai_timeout_seconds": 180.0,
        "llama_max_tokens": 700,
        "llama_seed": 42,
    }
    values.update(overrides)
    return Settings.model_validate(values)


def test_p3_settings_allow_cloudflare_without_changing_local_default() -> None:
    local = Settings(_env_file=None)
    remote = _cloudflare_settings()

    assert local.llm_runtime_provider == "llama_cpp"
    assert remote.llm_runtime_provider == "cloudflare_workers_ai"
    assert (
        remote.cloudflare_workers_ai_model
        == "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
    )


def test_p3_cloudflare_runtime_rejects_missing_credentials() -> None:
    with pytest.raises(CloudflareWorkersAIRuntimeError, match="CLOUDFLARE_ACCOUNT_ID"):
        build_cloudflare_workers_ai_provider(
            _cloudflare_settings(cloudflare_account_id=None)
        )

    with pytest.raises(CloudflareWorkersAIRuntimeError, match="CLOUDFLARE_AUTH_TOKEN"):
        build_cloudflare_workers_ai_provider(
            _cloudflare_settings(cloudflare_auth_token=None)
        )


def test_p3_cloudflare_runtime_descriptor_never_contains_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeCloudflareProvider:
        def __init__(
            self,
            account_id: str,
            auth_token: str,
            **kwargs: object,
        ) -> None:
            captured["account_id"] = account_id
            captured["auth_token"] = auth_token
            captured.update(kwargs)

        @property
        def provider_name(self) -> str:
            return "cloudflare_workers_ai"

        @property
        def model_name(self) -> str:
            return "@cf/meta/llama-3.3-70b-instruct-fp8-fast"

    monkeypatch.setattr(
        "app.services.cloudflare_workers_ai_runtime.CloudflareWorkersAIProvider",
        FakeCloudflareProvider,
    )

    provider, descriptor = build_cloudflare_workers_ai_provider(
        _cloudflare_settings()
    )

    assert provider.provider_name == "cloudflare_workers_ai"
    assert captured["account_id"] == _ACCOUNT_ID
    assert captured["auth_token"] == "test-secret"
    assert descriptor.provider_name == "cloudflare_workers_ai"
    assert descriptor.real_llama_active is True
    assert descriptor.external_llm_api_used is True
    assert descriptor.mock_runtime_allowed is False
    serialized = descriptor.model_dump_json()
    assert "test-secret" not in serialized
    assert _ACCOUNT_ID not in serialized


def test_p3_runtime_factory_selects_cloudflare_explicitly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = cast(CloudflareWorkersAIProvider, object())
    descriptor = CloudflareWorkersAIRuntimeDescriptor(
        model_name="@cf/meta/llama-3.3-70b-instruct-fp8-fast",
        base_url="https://api.cloudflare.com/client/v4",
        max_tokens=700,
        timeout_seconds=180.0,
    )
    observed: list[str] = []

    def build_cloudflare(
        _settings: Settings,
    ) -> tuple[CloudflareWorkersAIProvider, CloudflareWorkersAIRuntimeDescriptor]:
        observed.append("cloudflare_workers_ai")
        return provider, descriptor

    def fail_local(_settings: Settings) -> tuple[LlamaCppProvider, object]:
        raise AssertionError("No debe construir llama.cpp en modo Cloudflare.")

    def fail_openrouter(_settings: Settings) -> tuple[OpenRouterProvider, object]:
        raise AssertionError("No debe construir OpenRouter en modo Cloudflare.")

    monkeypatch.setattr(
        runtime_factory,
        "build_cloudflare_workers_ai_provider",
        build_cloudflare,
    )
    monkeypatch.setattr(runtime_factory, "build_real_llama_provider", fail_local)
    monkeypatch.setattr(
        runtime_factory,
        "build_openrouter_llama_provider",
        fail_openrouter,
    )

    selected_provider, selected_descriptor = runtime_factory._build_runtime_llama_provider(
        _cloudflare_settings()
    )

    assert selected_provider is provider
    assert selected_descriptor is descriptor
    assert observed == ["cloudflare_workers_ai"]
