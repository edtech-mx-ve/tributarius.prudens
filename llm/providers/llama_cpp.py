from __future__ import annotations

import importlib
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast

from llm.errors import LLMConfigurationError, LLMGenerationError
from llm.models import LLMGenerationContext
from llm.prompting import build_messages

_GRAMMAR_UNSAFE_SCHEMA_KEYS = frozenset(
    {
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
        "minProperties",
        "maxProperties",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "pattern",
        "format",
        "uniqueItems",
    }
)


def _grammar_safe_json_schema(value: object) -> object:
    """Reduce sólo restricciones que llama.cpp expande de forma explosiva.

    El esquema estructural se conserva para la gramática local. Las restricciones
    eliminadas siguen siendo obligatorias porque cada servicio valida después la
    salida con el modelo Pydantic canónico completo.
    """

    if isinstance(value, dict):
        sanitized: dict[str, object] = {}
        for key, item in value.items():
            if key in _GRAMMAR_UNSAFE_SCHEMA_KEYS:
                continue
            sanitized[key] = _grammar_safe_json_schema(item)
        return sanitized
    if isinstance(value, list):
        return [_grammar_safe_json_schema(item) for item in value]
    return value


class _LlamaBackend(Protocol):
    def create_chat_completion(
        self,
        *,
        messages: list[dict[str, str]],
        response_format: dict[str, object],
        temperature: float,
        max_tokens: int,
        seed: int,
    ) -> object:
        ...


class LlamaCppProvider:
    """Proveedor local CPU para modelos Llama en formato GGUF mediante llama.cpp."""

    def __init__(
        self,
        model_path: Path,
        *,
        n_ctx: int = 4096,
        max_tokens: int = 700,
        seed: int = 42,
        chat_format: str | None = None,
        n_threads: int = 1,
        n_batch: int = 128,
    ) -> None:
        resolved = model_path.expanduser().resolve()
        if not resolved.exists() or not resolved.is_file():
            raise LLMConfigurationError(f"No existe el modelo GGUF: {resolved}")
        if resolved.suffix.lower() != ".gguf":
            raise LLMConfigurationError("El modelo local debe usar formato .gguf.")
        if not 512 <= n_ctx <= 131072:
            raise LLMConfigurationError("n_ctx fuera del rango permitido.")
        if not 32 <= max_tokens <= 8192:
            raise LLMConfigurationError("max_tokens fuera del rango permitido.")
        if not 1 <= n_threads <= 256:
            raise LLMConfigurationError("n_threads fuera del rango permitido.")
        if not 8 <= n_batch <= 4096:
            raise LLMConfigurationError("n_batch fuera del rango permitido.")

        try:
            module = importlib.import_module("llama_cpp")
            factory = cast(Callable[..., _LlamaBackend], module.Llama)
        except (ImportError, AttributeError) as exc:
            raise LLMConfigurationError(
                "llama-cpp-python no está instalado. "
                "Instala el extra opcional del proyecto cuando quieras usar un GGUF real."
            ) from exc

        kwargs: dict[str, object] = {
            "model_path": str(resolved),
            "n_ctx": n_ctx,
            "n_gpu_layers": 0,
            "n_threads": n_threads,
            "n_threads_batch": n_threads,
            "n_batch": n_batch,
            "use_mmap": True,
            "use_mlock": False,
            "verbose": False,
        }
        if chat_format is not None:
            kwargs["chat_format"] = chat_format

        try:
            self._backend = factory(**kwargs)
        except (RuntimeError, ValueError, OSError) as exc:
            raise LLMConfigurationError(
                "No fue posible cargar el modelo GGUF local."
            ) from exc

        self._model_path = resolved
        self._max_tokens = max_tokens
        self._seed = seed
        self._last_generation_usage: dict[str, int | str | None] = {}

    @property
    def provider_name(self) -> str:
        return "llama-cpp-python"

    @property
    def model_name(self) -> str:
        return self._model_path.stem

    @property
    def last_generation_usage(self) -> dict[str, int | str | None]:
        """Metadatos de la última generación para diagnóstico F.12.1."""
        return dict(self._last_generation_usage)

    def generate_messages_json(
        self,
        messages: list[dict[str, str]],
        *,
        response_schema: dict[str, object],
    ) -> str:
        self._last_generation_usage = {}
        try:
            response = self._backend.create_chat_completion(
                messages=messages,
                response_format={
                    "type": "json_object",
                    "schema": _grammar_safe_json_schema(response_schema),
                },
                temperature=0.0,
                max_tokens=self._max_tokens,
                seed=self._seed,
            )
        except (RuntimeError, ValueError, OSError) as exc:
            raise LLMGenerationError("Falló la generación local con Llama.") from exc

        if not isinstance(response, dict):
            raise LLMGenerationError("El backend Llama devolvió una respuesta inválida.")

        usage = response.get("usage")
        observed_usage: dict[str, int | str | None] = {}
        if isinstance(usage, dict):
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                value = usage.get(key)
                if isinstance(value, int) and value >= 0:
                    observed_usage[key] = value

        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMGenerationError("La respuesta Llama no contiene choices.")

        first = choices[0]
        if not isinstance(first, dict):
            raise LLMGenerationError("Formato de choice inválido.")
        finish_reason = first.get("finish_reason")
        if finish_reason is not None:
            observed_usage["finish_reason"] = str(finish_reason)
        self._last_generation_usage = observed_usage

        message = first.get("message")
        if not isinstance(message, dict):
            raise LLMGenerationError("La respuesta Llama no contiene message.")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise LLMGenerationError("La respuesta Llama no contiene JSON utilizable.")
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
