from __future__ import annotations

import httpx
import pytest

from llm.errors import LLMConfigurationError, LLMGenerationError
from llm.providers.openrouter import OpenRouterProvider


def test_openrouter_rejects_missing_api_key() -> None:
    with pytest.raises(LLMConfigurationError, match="OPENROUTER_API_KEY"):
        OpenRouterProvider("   ")


def test_openrouter_sends_fixed_model_json_mode_and_schema() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("authorization")
        captured["body"] = request.read().decode("utf-8")
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": '{"answer":"ok"}'},
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 4,
                    "total_tokens": 14,
                },
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenRouterProvider(
        "test-key",
        model_name="meta-llama/llama-3.3-70b-instruct:free",
        max_tokens=321,
        seed=7,
        client=client,
    )

    result = provider.generate_messages_json(
        [{"role": "system", "content": "Devuelve JSON."}],
        response_schema={
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
        },
    )

    assert result == '{"answer":"ok"}'
    assert provider.provider_name == "openrouter"
    assert provider.model_name == "meta-llama/llama-3.3-70b-instruct:free"
    assert provider.last_generation_usage == {
        "prompt_tokens": 10,
        "completion_tokens": 4,
        "total_tokens": 14,
        "finish_reason": "stop",
    }
    assert captured["authorization"] == "Bearer test-key"

    import json

    body = json.loads(str(captured["body"]))
    assert body["model"] == "meta-llama/llama-3.3-70b-instruct:free"
    assert body["temperature"] == 0.0
    assert body["max_tokens"] == 321
    assert body["seed"] == 7
    assert body["response_format"] == {"type": "json_object"}
    system_content = body["messages"][0]["content"]
    assert "esquema JSON" in system_content
    assert '"required":["answer"]' in system_content


def test_openrouter_maps_http_failure_to_generation_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "rate limited"}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenRouterProvider("test-key", client=client)

    with pytest.raises(LLMGenerationError, match="OpenRouter"):
        provider.generate_messages_json(
            [{"role": "user", "content": "consulta"}],
            response_schema={"type": "object"},
        )
