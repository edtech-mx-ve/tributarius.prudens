from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from app.core.config import Settings
from app.services.hybrid_orchestrator import HybridOrchestrator
from app.services.normative_temporal_runtime_guard import (
    TemporalRuntimeGuardError,
    load_temporal_runtime_guard,
)
from app.services.rule_loader import RuleLoadError, load_rule_set
from app.web.runtime_runner import WebHybridRunner
from llm.providers.mock import MockLLMProvider
from llm.providers.runtime_query import RuntimeQueryAnalyzerProvider
from llm.query_analyzer import QueryAnalyzer
from llm.service import LlamaRAGService
from rag.embeddings.provider import EmbeddingError, SentenceTransformerEmbedder
from rag.indexing.models import IndexManifest
from rag.retrieval.legal_hybrid import LegalHybridRetriever
from rag.retrieval.retriever import FaissRetriever, RetrievalError

_REQUIRED_RAG_FILES = ("index.faiss", "chunks.jsonl", "manifest.json")


class RuntimeBuildError(RuntimeError):
    """Fallo controlado al construir el runtime de consulta."""


@dataclass(frozen=True)
class RuntimeComponents:
    runner: WebHybridRunner
    artifact_dir: Path
    model_name: str


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
    _validated_file(
        settings.runtime_rule_set_path,
        label="El conjunto de reglas",
        suffix=".json",
    )
    return artifact_dir, manifest


def build_runtime_components(settings: Settings) -> RuntimeComponents:
    artifact_dir, manifest = validate_runtime_assets(settings)

    embedder = SentenceTransformerEmbedder(
        manifest.model_name,
        device="cpu",
        local_files_only=settings.rag_local_files_only,
    )
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
        base_retriever = FaissRetriever(
            artifact_dir,
            embedder,
            verify_integrity=settings.verify_rag_integrity,
        )
        legal_retriever = LegalHybridRetriever.from_policy_file(
            base_retriever,
            Path(settings.legal_retrieval_policy_path),
        )
        rule_set = load_rule_set(Path(settings.runtime_rule_set_path))
    except (EmbeddingError, RetrievalError, RuleLoadError) as exc:
        raise RuntimeBuildError("No fue posible inicializar el runtime RAG.") from exc

    orchestrator = HybridOrchestrator(
        query_analyzer=QueryAnalyzer(RuntimeQueryAnalyzerProvider()),
        retriever=legal_retriever,
        llm_service=LlamaRAGService(MockLLMProvider()),
        rule_set=rule_set,
        temporal_guard=temporal_guard,
    )
    runner = WebHybridRunner(
        orchestrator=orchestrator,
        retrieval_runtime="legal_hybrid_19g",
        explanation_runtime="deterministic_mock_until_sprint20",
    )
    return RuntimeComponents(
        runner=runner,
        artifact_dir=artifact_dir,
        model_name=manifest.model_name,
    )
