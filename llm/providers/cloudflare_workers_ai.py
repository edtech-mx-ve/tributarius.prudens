from __future__ import annotations

import json
import re
from urllib.parse import quote, urlsplit

import httpx

from llm.errors import LLMConfigurationError, LLMGenerationError
from llm.models import LLMGenerationContext
from llm.prompting import build_messages

_DEFAULT_BASE_URL = "https://api.cloudflare.com/client/v4"
_ACCOUNT_ID_RE = re.compile(r"^[A-Fa-f0-9]{32}$")


class CloudflareWorkersAIProvider:
    """Proveedor Llama remoto para el prototipo web mediante Workers AI."""

    def __init__(
        self,
        account_id: str,
        auth_token: str,
        *,
        model_name: str = "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
        base_url: str = _DEFAULT_BASE_URL,
        max_tokens: int = 700,
        seed: int = 42,
        timeout_seconds: float = 180.0,
        client: httpx.Client | None = None,
    ) -> None:
        normalized_account_id = account_id.strip()
        if not _ACCOUNT_ID_RE.fullmatch(normalized_account_id):
            raise LLMConfigurationError(
                "CLOUDFLARE_ACCOUNT_ID debe contener 32 caracteres hexadecimales."
            )

        normalized_token = auth_token.strip()
        if not normalized_token:
            raise LLMConfigurationError("CLOUDFLARE_AUTH_TOKEN es obligatorio.")

        normalized_model = model_name.strip()
        if not normalized_model.startswith("@cf/"):
            raise LLMConfigurationError(
                "CLOUDFLARE_WORKERS_AI_MODEL debe ser un modelo Workers AI @cf/."
            )

        normalized_base_url = base_url.strip().rstrip("/")
        parsed = urlsplit(normalized_base_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise LLMConfigurationError(
                "CLOUDFLARE_WORKERS_AI_BASE_URL debe ser una URL HTTPS válida."
            )
        if not 32 <= max_tokens <= 8192:
            raise LLMConfigurationError("max_tokens fuera del rango permitido.")
        if timeout_seconds <= 0:
            raise LLMConfigurationError("timeout_seconds debe ser mayor que cero.")

        self._account_id = normalized_account_id
        self._auth_token = normalized_token
        self._model_name = normalized_model
        self._base_url = normalized_base_url
        self._max_tokens = max_tokens
        self._seed = seed
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._last_generation_usage: dict[str, int | float | str | None] = {}

    @property
    def provider_name(self) -> str:
        return "cloudflare_workers_ai"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def last_generation_usage(self) -> dict[str, int | float | str | None]:
        """Metadatos no secretos de la última generación."""
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

    def _endpoint(self) -> str:
        encoded_model = quote(self._model_name, safe="@/-_.")
        return (
            f"{self._base_url}/accounts/{self._account_id}/ai/run/{encoded_model}"
        )

    @staticmethod
    def _cloudflare_error_message(response: httpx.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            return "sin detalle"
        if not isinstance(body, dict):
            return "sin detalle"
        errors = body.get("errors")
        if isinstance(errors, list):
            for item in errors:
                if isinstance(item, dict):
                    message = item.get("message")
                    if isinstance(message, str) and message.strip():
                        return message.strip()[:300]
        return "sin detalle"

    def generate_messages_json(
        self,
        messages: list[dict[str, str]],
        *,
        response_schema: dict[str, object],
    ) -> str:
        self._last_generation_usage = {}
        payload: dict[str, object] = {
            "messages": self._messages_with_schema(messages, response_schema),
            "temperature": 0.0,
            "max_tokens": self._max_tokens,
            "seed": self._seed,
            "response_format": {
                "type": "json_schema",
                "json_schema": response_schema,
            },
        }
        headers = {
            "Authorization": f"Bearer {self._auth_token}",
            "Content-Type": "application/json",
        }

        try:
            response = self._client.post(
                self._endpoint(),
                headers=headers,
                json=payload,
            )
        except httpx.RequestError as exc:
            raise LLMGenerationError(
                "Falló la conexión remota con Cloudflare Workers AI."
            ) from exc

        if response.is_error:
            detail = self._cloudflare_error_message(response)
            raise LLMGenerationError(
                "Falló la generación remota con Cloudflare Workers AI "
                f"(HTTP {response.status_code}; {detail})."
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise LLMGenerationError(
                "Cloudflare Workers AI devolvió JSON HTTP inválido."
            ) from exc

        if not isinstance(body, dict) or body.get("success") is not True:
            raise LLMGenerationError(
                "Cloudflare Workers AI devolvió una respuesta no exitosa."
            )
        result = body.get("result")
        if not isinstance(result, dict):
            raise LLMGenerationError(
                "Cloudflare Workers AI no devolvió un objeto result válido."
            )

        observed_usage: dict[str, int | float | str | None] = {}
        usage = result.get("usage")
        if isinstance(usage, dict):
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                value = usage.get(key)
                if isinstance(value, int) and value >= 0:
                    observed_usage[key] = value
            neurons = usage.get("neurons")
            if isinstance(neurons, (int, float)) and not isinstance(neurons, bool):
                observed_usage["neurons"] = float(neurons)

        routed_model = result.get("model")
        if isinstance(routed_model, str) and routed_model.strip():
            observed_usage["routed_model"] = routed_model.strip()

        choices = result.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            finish_reason = choices[0].get("finish_reason")
            if finish_reason is not None:
                observed_usage["finish_reason"] = str(finish_reason)
        self._last_generation_usage = observed_usage

        structured = result.get("response")
        if isinstance(structured, dict):
            return json.dumps(structured, ensure_ascii=False, separators=(",", ":"))
        if isinstance(structured, str) and structured.strip():
            return structured

        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            message = choices[0].get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return content

        raise LLMGenerationError(
            "Cloudflare Workers AI no devolvió JSON estructurado utilizable."
        )

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
