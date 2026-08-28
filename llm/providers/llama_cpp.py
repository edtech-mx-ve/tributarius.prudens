from __future__ import annotations

import importlib
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast

from llm.errors import LLMConfigurationError, LLMGenerationError
from llm.models import LLMGenerationContext
from llm.prompting import build_messages


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

    @property
    def provider_name(self) -> str:
        return "llama-cpp-python"

    @property
    def model_name(self) -> str:
        return self._model_path.stem

    def generate_messages_json(
        self,
        messages: list[dict[str, str]],
        *,
        response_schema: dict[str, object],
    ) -> str:
        try:
            response = self._backend.create_chat_completion(
                messages=messages,
                response_format={
                    "type": "json_object",
                    "schema": response_schema,
                },
                temperature=0.0,
                max_tokens=self._max_tokens,
                seed=self._seed,
            )
        except (RuntimeError, ValueError, OSError) as exc:
            raise LLMGenerationError("Falló la generación local con Llama.") from exc

        if not isinstance(response, dict):
            raise LLMGenerationError("El backend Llama devolvió una respuesta inválida.")
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMGenerationError("La respuesta Llama no contiene choices.")

        first = choices[0]
        if not isinstance(first, dict):
            raise LLMGenerationError("Formato de choice inválido.")
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
