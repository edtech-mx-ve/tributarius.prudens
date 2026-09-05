from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from app.core.config import Settings
from app.domain.cloudflare_workers_ai_runtime import CloudflareWorkersAIRuntimeDescriptor
from app.domain.openrouter_llama_runtime import OpenRouterLlamaRuntimeDescriptor
from app.domain.real_llama_runtime import RealLlamaRuntimeDescriptor
from app.services.cloudflare_workers_ai_runtime import (
    CloudflareWorkersAIRuntimeError,
    build_cloudflare_workers_ai_provider,
)
from app.services.hybrid_llama_runtime import (
    HybridLlamaRuntime,
    build_hybrid_llama_service_bundle,
)
from app.services.hybrid_orchestrator import HybridOrchestrator
from app.services.normative_temporal_runtime_guard import (
    TemporalRuntimeGuardError,
    load_temporal_runtime_guard,
)
from app.services.openrouter_llama_runtime import (
    OpenRouterLlamaRuntimeError,
    build_openrouter_llama_provider,
)
from app.services.primary_rbs_inventory import (
    CurrentRBSInventoryError,
    load_current_production_rule_set,
)
from app.services.real_llama_runtime import (
    RealLlamaRuntimeError,
    build_real_llama_provider,
)
from app.services.rule_loader import RuleLoadError, load_rule_set
from app.web.runtime_runner import WebHybridRunner
from llm.providers.cloudflare_workers_ai import CloudflareWorkersAIProvider
from llm.providers.llama_cpp import LlamaCppProvider
from llm.providers.openrouter import OpenRouterProvider
from llm.providers.runtime_query import RuntimeQueryAnalyzerProvider
from llm.query_analyzer import QueryAnalyzer
from llm.service import LlamaRAGService
from rag.embeddings.provider import EmbeddingError, SentenceTransformerEmbedder
from rag.indexing.models import IndexManifest
from rag.retrieval.legal_hybrid import LegalHybridRetriever, RetrieverLike
from rag.retrieval.lexical_cpu import CpuLexicalRetriever
from rag.retrieval.retriever import FaissRetriever, RetrievalError

_REQUIRED_RAG_FILES = ("index.faiss", "chunks.jsonl", "manifest.json")
_ALLOWED_RUNTIME_BACKENDS = frozenset({"semantic", "lexical_cpu"})


class RuntimeBuildError(RuntimeError):
    """Fallo controlado al construir el runtime de consulta."""


@dataclass(frozen=True)
class RuntimeComponents:
    runner: WebHybridRunner
    artifact_dir: Path
    model_name: str
    llama_runtime: (
        RealLlamaRuntimeDescriptor
        | OpenRouterLlamaRuntimeDescriptor
        | CloudflareWorkersAIRuntimeDescriptor
    )
    retrieval_backend: str = "semantic"


def _validated_file(path_value: str, *, label: str, suffix: str) -> Path:
    path = Path(path_value).expanduser().resolve()
    if not path.is_file() or path.suffix.casefold() != suffix:
        raise RuntimeBuildError(f"{label} no está disponible o tiene formato inválido.")
    return path


def _load_manifest(artifact_dir: Path) -> IndexManifest:
    manifest_path = artifact_dir / "manifest.json"
    try:
        return IndexManifest.model_validate_json(
            manifest_path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, ValidationError) as exc:
        raise RuntimeBuildError("manifest.json del runtime RAG es inválido.") from exc


def validate_runtime_assets(settings: Settings) -> tuple[Path, IndexManifest]:
    artifact_dir = Path(settings.rag_artifact_dir).expanduser().resolve()
    missing = [name for name in _REQUIRED_RAG_FILES if not (artifact_dir / name).is_file()]
    if missing:
        raise RuntimeBuildError(
            "Faltan artefactos RAG requeridos: " + ", ".join(sorted(missing))
        )

    manifest = _load_manifest(artifact_dir)
    _validated_file(
        settings.legal_retrieval_policy_path,
        label="La política de recuperación jurídica",
        suffix=".json",
    )
    if settings.environment == "production":
        inventory_path = _validated_file(
            settings.runtime_rbs_inventory_path,
            label="El inventario RBS B.1",
            suffix=".json",
        )
        production_dir = Path(settings.runtime_rule_set_dir).expanduser().resolve()
        if not production_dir.is_dir():
            raise RuntimeBuildError(
                "El directorio de reglas RBS de producci?n no est? disponible."
            )
        try:
            load_current_production_rule_set(
                inventory_path,
                production_dir,
            )
        except CurrentRBSInventoryError as exc:
            raise RuntimeBuildError(
                "El RBS productivo no coincide con el inventario B.1."
            ) from exc
    else:
        _validated_file(
            settings.runtime_rule_set_path,
            label="El conjunto de reglas",
            suffix=".json",
        )

    return artifact_dir, manifest


def runtime_backend_name() -> str:
    """Backend explícito y validado; nunca degrada silenciosamente."""
    raw = os.environ.get("RAG_RUNTIME_BACKEND", "semantic")
    backend = raw.strip().casefold()
    if backend not in _ALLOWED_RUNTIME_BACKENDS:
        allowed = ", ".join(sorted(_ALLOWED_RUNTIME_BACKENDS))
        raise RuntimeBuildError(
            f"RAG_RUNTIME_BACKEND inválido. Valores permitidos: {allowed}."
        )
    return backend


def _runtime_initialization_error(exc: Exception) -> RuntimeBuildError:
    """Conserva diagnóstico técnico acotado sin exponer contexto de petición."""
    detail = str(exc).strip() or "<sin detalle>"
    return RuntimeBuildError(
        "No fue posible inicializar el runtime RAG. "
        f"root_type={type(exc).__name__} root_cause={detail}"
    )


def _build_base_retriever(
    *,
    backend: str,
    artifact_dir: Path,
    manifest: IndexManifest,
    settings: Settings,
) -> RetrieverLike:
    if backend == "lexical_cpu":
        return CpuLexicalRetriever(
            artifact_dir,
            verify_integrity=settings.verify_rag_integrity,
        )

    embedder = SentenceTransformerEmbedder(
        manifest.model_name,
        device="cpu",
        local_files_only=settings.rag_local_files_only,
    )
    return FaissRetriever(
        artifact_dir,
        embedder,
        verify_integrity=settings.verify_rag_integrity,
    )




def _build_runtime_llama_provider(
    settings: Settings,
) -> tuple[
    LlamaCppProvider | OpenRouterProvider | CloudflareWorkersAIProvider,
    (
        RealLlamaRuntimeDescriptor
        | OpenRouterLlamaRuntimeDescriptor
        | CloudflareWorkersAIRuntimeDescriptor
    ),
]:
    """Selecciona explícitamente el proveedor real; nunca degrada a mock."""

    if settings.llm_runtime_provider == "openrouter":
        return build_openrouter_llama_provider(settings)
    if settings.llm_runtime_provider == "cloudflare_workers_ai":
        return build_cloudflare_workers_ai_provider(settings)
    return build_real_llama_provider(settings)


def build_runtime_llama_provider(
    settings: Settings,
) -> tuple[
    LlamaCppProvider | OpenRouterProvider | CloudflareWorkersAIProvider,
    (
        RealLlamaRuntimeDescriptor
        | OpenRouterLlamaRuntimeDescriptor
        | CloudflareWorkersAIRuntimeDescriptor
    ),
]:
    """API pública para seleccionar el proveedor Llama real del runtime."""

    return _build_runtime_llama_provider(settings)


def build_runtime_components(settings: Settings) -> RuntimeComponents:
    artifact_dir, manifest = validate_runtime_assets(settings)
    backend = runtime_backend_name()

    temporal_registry_path = Path(
        settings.temporal_provenance_registry_path
    ).expanduser().resolve()
    temporal_guard = None
    if temporal_registry_path.is_file():
        try:
            temporal_guard = load_temporal_runtime_guard(temporal_registry_path)
        except TemporalRuntimeGuardError as exc:
            raise RuntimeBuildError(
                "El registro temporal de procedencia es inválido."
            ) from exc
    elif settings.require_temporal_provenance_registry:
        raise RuntimeBuildError(
            "Se requiere registro temporal de procedencia y no está disponible."
        )

    try:
        base_retriever = _build_base_retriever(
            backend=backend,
            artifact_dir=artifact_dir,
            manifest=manifest,
            settings=settings,
        )
        legal_retriever = LegalHybridRetriever.from_policy_file(
            base_retriever,
            Path(settings.legal_retrieval_policy_path),
        )
        if settings.environment == "production":
            rule_set = load_current_production_rule_set(
                Path(settings.runtime_rbs_inventory_path),
                Path(settings.runtime_rule_set_dir),
            )
        else:
            rule_set = load_rule_set(Path(settings.runtime_rule_set_path))
    except (
        EmbeddingError,
        RetrievalError,
        RuleLoadError,
        CurrentRBSInventoryError,
    ) as exc:
        raise _runtime_initialization_error(exc) from exc

    try:
        llama_provider, llama_descriptor = build_runtime_llama_provider(settings)
    except RealLlamaRuntimeError as exc:
        raise RuntimeBuildError(
            "F.11 exige un Llama GGUF real y verificable para construir el runtime."
        ) from exc
    except OpenRouterLlamaRuntimeError as exc:
        raise RuntimeBuildError(
            "El prototipo web exige un Llama remoto real y verificable."
        ) from exc
    except CloudflareWorkersAIRuntimeError as exc:
        raise RuntimeBuildError(
            "El prototipo web exige un Llama remoto real y verificable."
        ) from exc

    llama_services = build_hybrid_llama_service_bundle(llama_provider)
    orchestrator = HybridOrchestrator(
        query_analyzer=QueryAnalyzer(RuntimeQueryAnalyzerProvider()),
        retriever=legal_retriever,
        llm_service=LlamaRAGService(llama_provider),
        rule_set=rule_set,
        temporal_guard=temporal_guard,
        hybrid_h1_service=llama_services.h1,
    )
    hybrid_llama_runtime = HybridLlamaRuntime(
        orchestrator=orchestrator,
        services=llama_services,
        provider_is_test_double=False,
    )
    explanation_runtime = f"llama_cpp_real:{llama_provider.model_name}"
    if llama_provider.provider_name == "openrouter":
        explanation_runtime = f"openrouter_real:{llama_provider.model_name}"
    elif llama_provider.provider_name == "cloudflare_workers_ai":
        explanation_runtime = (
            f"cloudflare_workers_ai_real:{llama_provider.model_name}"
        )

    runner = WebHybridRunner(
        orchestrator=orchestrator,
        retrieval_runtime=(
            "legal_hybrid_lexical_cpu_19s_r14"
            if backend == "lexical_cpu"
            else "legal_hybrid_19g"
        ),
        explanation_runtime=explanation_runtime,
        hybrid_llama_runtime=hybrid_llama_runtime,
    )
    return RuntimeComponents(
        runner=runner,
        artifact_dir=artifact_dir,
        model_name=manifest.model_name,
        llama_runtime=llama_descriptor,
        retrieval_backend=backend,
    )
