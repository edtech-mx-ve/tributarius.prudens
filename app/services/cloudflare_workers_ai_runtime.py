from __future__ import annotations

from app.core.config import Settings
from app.domain.cloudflare_workers_ai_runtime import CloudflareWorkersAIRuntimeDescriptor
from llm.errors import LLMConfigurationError
from llm.providers.cloudflare_workers_ai import CloudflareWorkersAIProvider


class CloudflareWorkersAIRuntimeError(RuntimeError):
    """La configuración no permite activar Cloudflare Workers AI."""


def build_cloudflare_workers_ai_provider(
    settings: Settings,
) -> tuple[CloudflareWorkersAIProvider, CloudflareWorkersAIRuntimeDescriptor]:
    """Construye el proveedor Llama remoto sin exponer token ni Account ID."""

    if settings.llm_runtime_provider != "cloudflare_workers_ai":
        raise CloudflareWorkersAIRuntimeError(
            "El runtime Cloudflare exige LLM_RUNTIME_PROVIDER=cloudflare_workers_ai."
        )
    if not settings.require_real_llama:
        raise CloudflareWorkersAIRuntimeError(
            "El runtime exige REQUIRE_REAL_LLAMA=true; no se permite mock."
        )

    account_id = (settings.cloudflare_account_id or "").strip()
    if not account_id:
        raise CloudflareWorkersAIRuntimeError(
            "CLOUDFLARE_ACCOUNT_ID es obligatorio para el prototipo web."
        )
    auth_token = (settings.cloudflare_auth_token or "").strip()
    if not auth_token:
        raise CloudflareWorkersAIRuntimeError(
            "CLOUDFLARE_AUTH_TOKEN es obligatorio para el prototipo web."
        )

    try:
        provider = CloudflareWorkersAIProvider(
            account_id,
            auth_token,
            model_name=settings.cloudflare_workers_ai_model,
            base_url=settings.cloudflare_workers_ai_base_url,
            max_tokens=settings.llama_max_tokens,
            seed=settings.llama_seed,
            timeout_seconds=settings.cloudflare_workers_ai_timeout_seconds,
        )
    except LLMConfigurationError as exc:
        raise CloudflareWorkersAIRuntimeError(
            "No fue posible inicializar el proveedor Cloudflare Workers AI autorizado."
        ) from exc

    descriptor = CloudflareWorkersAIRuntimeDescriptor(
        model_name=provider.model_name,
        base_url=settings.cloudflare_workers_ai_base_url.rstrip("/"),
        max_tokens=settings.llama_max_tokens,
        timeout_seconds=settings.cloudflare_workers_ai_timeout_seconds,
    )
    return provider, descriptor
