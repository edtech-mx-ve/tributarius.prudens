from __future__ import annotations

import hashlib
from pathlib import Path

from app.core.config import Settings
from app.domain.real_llama_runtime import RealLlamaRuntimeDescriptor
from llm.errors import LLMConfigurationError
from llm.providers.llama_cpp import LlamaCppProvider


class RealLlamaRuntimeError(RuntimeError):
    """La configuración F.11 no permite activar Llama real de forma verificable."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise RealLlamaRuntimeError("No fue posible leer el modelo GGUF.") from exc
    return digest.hexdigest()


def validate_real_llama_model(settings: Settings) -> tuple[Path, str]:
    """Valida existencia, formato e integridad del GGUF antes de cargar llama.cpp."""

    if settings.llm_runtime_provider != "llama_cpp":
        raise RealLlamaRuntimeError(
            "F.11 exige LLM_RUNTIME_PROVIDER=llama_cpp; el mock no es válido en runtime."
        )
    if not settings.require_real_llama:
        raise RealLlamaRuntimeError("F.11 exige REQUIRE_REAL_LLAMA=true en runtime.")

    model_path = Path(settings.llama_model_path).expanduser().resolve()
    if not model_path.is_file() or model_path.suffix.casefold() != ".gguf":
        raise RealLlamaRuntimeError("El modelo Llama GGUF real no está disponible.")

    actual_sha256 = _sha256_file(model_path)
    if actual_sha256 != settings.llama_model_sha256:
        raise RealLlamaRuntimeError(
            "El SHA-256 del modelo GGUF no coincide con el valor autorizado."
        )
    return model_path, actual_sha256


def build_real_llama_provider(
    settings: Settings,
) -> tuple[LlamaCppProvider, RealLlamaRuntimeDescriptor]:
    """Construye el único proveedor LLM permitido por F.11 para runtime real."""

    model_path, model_sha256 = validate_real_llama_model(settings)
    try:
        provider = LlamaCppProvider(
            model_path,
            n_ctx=settings.llama_n_ctx,
            max_tokens=settings.llama_max_tokens,
            seed=settings.llama_seed,
            chat_format=settings.llama_chat_format,
            n_threads=settings.llama_n_threads,
            n_batch=settings.llama_n_batch,
        )
    except LLMConfigurationError as exc:
        raise RealLlamaRuntimeError(
            "No fue posible inicializar LlamaCppProvider con el GGUF autorizado."
        ) from exc

    descriptor = RealLlamaRuntimeDescriptor(
        model_name=provider.model_name,
        model_path=str(model_path),
        model_sha256=model_sha256,
        n_ctx=settings.llama_n_ctx,
        max_tokens=settings.llama_max_tokens,
        n_threads=settings.llama_n_threads,
        n_batch=settings.llama_n_batch,
    )
    return provider, descriptor
