from __future__ import annotations

from typing import cast

import pytest

from app.core.config import Settings
from app.domain.cloudflare_workers_ai_runtime import CloudflareWorkersAIRuntimeDescriptor
from app.services import runtime_factory
from llm.providers.cloudflare_workers_ai import CloudflareWorkersAIProvider
from scripts.run_hybrid_llama_benchmark_f12 import _model_sha256_for_report


def test_p4_public_runtime_selector_uses_cloudflare(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = cast(CloudflareWorkersAIProvider, object())
    descriptor = CloudflareWorkersAIRuntimeDescriptor(
        model_name="@cf/meta/llama-3.3-70b-instruct-fp8-fast",
        base_url="https://api.cloudflare.com/client/v4",
        max_tokens=700,
        timeout_seconds=180.0,
    )

    def build_cloudflare(
        _settings: Settings,
    ) -> tuple[CloudflareWorkersAIProvider, CloudflareWorkersAIRuntimeDescriptor]:
        return provider, descriptor

    monkeypatch.setattr(
        runtime_factory,
        "build_cloudflare_workers_ai_provider",
        build_cloudflare,
    )

    settings = Settings(
        _env_file=None,
        llm_runtime_provider="cloudflare_workers_ai",
        cloudflare_account_id="a" * 32,
        cloudflare_auth_token="token",
    )
    selected_provider, selected_descriptor = runtime_factory.build_runtime_llama_provider(
        settings
    )

    assert selected_provider is provider
    assert selected_descriptor == descriptor


def test_p4_remote_descriptor_has_explicit_non_applicable_sha256() -> None:
    descriptor = CloudflareWorkersAIRuntimeDescriptor(
        model_name="@cf/meta/llama-3.3-70b-instruct-fp8-fast",
        base_url="https://api.cloudflare.com/client/v4",
        max_tokens=700,
        timeout_seconds=180.0,
    )

    assert _model_sha256_for_report(descriptor) == "not_applicable_remote_provider"
