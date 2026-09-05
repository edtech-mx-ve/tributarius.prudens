from __future__ import annotations

import json

import httpx
import pytest

from llm.errors import LLMConfigurationError, LLMGenerationError
from llm.providers.cloudflare_workers_ai import CloudflareWorkersAIProvider

_ACCOUNT_ID = "0123456789abcdef0123456789abcdef"


def test_cloudflare_rejects_invalid_account_id() -> None:
    with pytest.raises(LLMConfigurationError, match="CLOUDFLARE_ACCOUNT_ID"):
        CloudflareWorkersAIProvider("bad", "token")


def test_cloudflare_rejects_missing_auth_token() -> None:
    with pytest.raises(LLMConfigurationError, match="CLOUDFLARE_AUTH_TOKEN"):
        CloudflareWorkersAIProvider(_ACCOUNT_ID, "   ")


def test_cloudflare_sends_json_schema_and_records_routed_model() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("authorization")
        captured["url"] = str(request.url)
        captured["body"] = request.read().decode("utf-8")
        return httpx.Response(
            200,
            json={
                "result": {
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {
                                "content": '{"answer":"ok"}',
                                "role": "assistant",
                            },
                        }
                    ],
                    "model": "@cf/meta/llama-3.3-70b-json",
                    "response": {"answer": "ok"},
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 4,
                        "total_tokens": 14,
                        "neurons": 5.25,
                    },
                },
                "success": True,
                "errors": [],
                "messages": [],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = CloudflareWorkersAIProvider(
        _ACCOUNT_ID,
        "test-token",
        model_name="@cf/meta/llama-3.3-70b-instruct-fp8-fast",
        max_tokens=321,
        seed=7,
        client=client,
    )
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
        "additionalProperties": False,
    }

    result = provider.generate_messages_json(
        [{"role": "system", "content": "Devuelve JSON."}],
        response_schema=schema,
    )

    assert result == '{"answer":"ok"}'
    assert provider.provider_name == "cloudflare_workers_ai"
    assert provider.model_name == "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
    assert provider.last_generation_usage == {
        "prompt_tokens": 10,
        "completion_tokens": 4,
        "total_tokens": 14,
        "neurons": 5.25,
        "routed_model": "@cf/meta/llama-3.3-70b-json",
        "finish_reason": "stop",
    }
    assert captured["authorization"] == "Bearer test-token"
    assert str(captured["url"]).endswith(
        "/accounts/0123456789abcdef0123456789abcdef/ai/run/"
        "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
    )

    body = json.loads(str(captured["body"]))
    assert body["temperature"] == 0.0
    assert body["max_tokens"] == 321
    assert body["seed"] == 7
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": schema,
    }
    assert "esquema JSON" in body["messages"][0]["content"]


def test_cloudflare_falls_back_to_choice_message_content() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "result": {
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {"content": '{"answer":"fallback"}'},
                        }
                    ],
                    "usage": {},
                },
                "success": True,
                "errors": [],
                "messages": [],
            },
        )

    provider = CloudflareWorkersAIProvider(
        _ACCOUNT_ID,
        "test-token",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert provider.generate_messages_json(
        [{"role": "user", "content": "consulta"}],
        response_schema={"type": "object"},
    ) == '{"answer":"fallback"}'


def test_cloudflare_maps_http_failure_without_secret() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={
                "success": False,
                "errors": [{"message": "rate limited"}],
            },
        )

    provider = CloudflareWorkersAIProvider(
        _ACCOUNT_ID,
        "super-secret-token",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(LLMGenerationError, match="HTTP 429") as exc_info:
        provider.generate_messages_json(
            [{"role": "user", "content": "consulta"}],
            response_schema={"type": "object"},
        )

    assert "rate limited" in str(exc_info.value)
    assert "super-secret-token" not in str(exc_info.value)
