from __future__ import annotations

import json
from urllib.parse import urlsplit

import httpx

from llm.errors import LLMConfigurationError, LLMGenerationError
from llm.models import LLMGenerationContext
from llm.prompting import build_messages

_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider:
    """Proveedor Llama remoto para el prototipo web mediante OpenRouter."""

    def __init__(
        self,
        api_key: str,
        *,
        model_name: str = "meta-llama/llama-3.3-70b-instruct:free",
        base_url: str = _DEFAULT_BASE_URL,
        max_tokens: int = 700,
        seed: int = 42,
        timeout_seconds: float = 180.0,
        client: httpx.Client | None = None,
    ) -> None:
        normalized_key = api_key.strip()
        if not normalized_key:
            raise LLMConfigurationError("OPENROUTER_API_KEY es obligatorio.")

        normalized_model = model_name.strip()
        if not normalized_model:
            raise LLMConfigurationError("OPENROUTER_MODEL no puede estar vacío.")

        normalized_base_url = base_url.strip().rstrip("/")
        parsed = urlsplit(normalized_base_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise LLMConfigurationError("OPENROUTER_BASE_URL debe ser una URL HTTPS válida.")
        if not 32 <= max_tokens <= 8192:
            raise LLMConfigurationError("max_tokens fuera del rango permitido.")
        if timeout_seconds <= 0:
            raise LLMConfigurationError("timeout_seconds debe ser mayor que cero.")

        self._api_key = normalized_key
        self._model_name = normalized_model
        self._base_url = normalized_base_url
        self._max_tokens = max_tokens
        self._seed = seed
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._last_generation_usage: dict[str, int | str | None] = {}

    @property
    def provider_name(self) -> str:
        return "openrouter"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def last_generation_usage(self) -> dict[str, int | str | None]:
        """Metadatos de la última generación para diagnóstico del prototipo web."""
        return dict(self._last_generation_usage)

    @staticmethod
    def _messages_with_schema(
        messages: list[dict[str, str]],
        response_schema: dict[str, object],
    ) -> list[dict[str, str]]:
        prepared = [dict(message) for message in messages]
        schema_text = json.dumps(
            response_schema,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        schema_instruction = (
            "\nDevuelve exclusivamente un objeto JSON que cumpla este esquema JSON: "
            f"{schema_text}"
        )
        if prepared and prepared[0].get("role") == "system":
            prepared[0]["content"] = prepared[0].get("content", "") + schema_instruction
        else:
            prepared.insert(0, {"role": "system", "content": schema_instruction.strip()})
        return prepared

    def generate_messages_json(
        self,
        messages: list[dict[str, str]],
        *,
        response_schema: dict[str, object],
    ) -> str:
        self._last_generation_usage = {}
        payload: dict[str, object] = {
            "model": self._model_name,
            "messages": self._messages_with_schema(messages, response_schema),
            "temperature": 0.0,
            "max_tokens": self._max_tokens,
            "seed": self._seed,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = self._client.post(
                f"{self._base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as exc:
            raise LLMGenerationError("Falló la generación remota con OpenRouter.") from exc

        if not isinstance(body, dict):
            raise LLMGenerationError("OpenRouter devolvió una respuesta inválida.")

        usage = body.get("usage")
        observed_usage: dict[str, int | str | None] = {}
        if isinstance(usage, dict):
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                value = usage.get(key)
                if isinstance(value, int) and value >= 0:
                    observed_usage[key] = value

        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMGenerationError("La respuesta OpenRouter no contiene choices.")
        first = choices[0]
        if not isinstance(first, dict):
            raise LLMGenerationError("Formato de choice inválido en OpenRouter.")

        finish_reason = first.get("finish_reason")
        if finish_reason is not None:
            observed_usage["finish_reason"] = str(finish_reason)
        self._last_generation_usage = observed_usage

        message = first.get("message")
        if not isinstance(message, dict):
            raise LLMGenerationError("La respuesta OpenRouter no contiene message.")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise LLMGenerationError("La respuesta OpenRouter no contiene JSON utilizable.")
        return content

    def generate_json(
        self,
        context: LLMGenerationContext,
        *,
        response_schema: dict[str, object],
    ) -> str:
        return self.generate_messages_json(
            build_messages(context),
            response_schema=response_schema,
        )
