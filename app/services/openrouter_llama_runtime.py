from __future__ import annotations

from app.core.config import Settings
from app.domain.openrouter_llama_runtime import OpenRouterLlamaRuntimeDescriptor
from llm.errors import LLMConfigurationError
from llm.providers.openrouter import OpenRouterProvider


class OpenRouterLlamaRuntimeError(RuntimeError):
    """La configuración del prototipo web no permite activar OpenRouter."""


def build_openrouter_llama_provider(
    settings: Settings,
) -> tuple[OpenRouterProvider, OpenRouterLlamaRuntimeDescriptor]:
    """Construye un proveedor Llama remoto verificable sin exponer la API key."""

    if settings.llm_runtime_provider != "openrouter":
        raise OpenRouterLlamaRuntimeError(
            "El runtime OpenRouter exige LLM_RUNTIME_PROVIDER=openrouter."
        )
    if not settings.require_real_llama:
        raise OpenRouterLlamaRuntimeError(
            "El runtime exige REQUIRE_REAL_LLAMA=true; no se permite mock."
        )

    api_key = (settings.openrouter_api_key or "").strip()
    if not api_key:
        raise OpenRouterLlamaRuntimeError(
            "OPENROUTER_API_KEY es obligatorio para el prototipo web."
        )

    try:
        provider = OpenRouterProvider(
            api_key,
            model_name=settings.openrouter_model,
            base_url=settings.openrouter_base_url,
            max_tokens=settings.llama_max_tokens,
            seed=settings.llama_seed,
            timeout_seconds=settings.openrouter_timeout_seconds,
        )
    except LLMConfigurationError as exc:
        raise OpenRouterLlamaRuntimeError(
            "No fue posible inicializar el proveedor OpenRouter autorizado."
        ) from exc

    descriptor = OpenRouterLlamaRuntimeDescriptor(
        model_name=provider.model_name,
        base_url=settings.openrouter_base_url.rstrip("/"),
        max_tokens=settings.llama_max_tokens,
        timeout_seconds=settings.openrouter_timeout_seconds,
    )
    return provider, descriptor
