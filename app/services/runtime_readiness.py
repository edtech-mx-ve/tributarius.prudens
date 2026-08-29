from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from app.core.config import Settings
from app.core.database import database_session
from app.domain.deployment import ReadinessReport, ReadinessState, RuntimeCapability

_REQUIRED_RAG_FILES = ("index.faiss", "chunks.jsonl", "manifest.json")


def _database_capability() -> RuntimeCapability:
    try:
        with database_session() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        return RuntimeCapability(
            name="database",
            available=False,
            detail="La base de datos no respondió a SELECT 1.",
        )
    return RuntimeCapability(
        name="database",
        available=True,
        detail="Conectividad SQL disponible.",
    )


def _rag_capability(settings: Settings) -> RuntimeCapability:
    directory = Path(settings.rag_artifact_dir).expanduser()
    missing = [name for name in _REQUIRED_RAG_FILES if not (directory / name).is_file()]
    if missing:
        return RuntimeCapability(
            name="rag_artifacts",
            available=False,
            detail="Artefactos RAG ausentes: " + ", ".join(missing),
        )
    return RuntimeCapability(
        name="rag_artifacts",
        available=True,
        detail="Índice, chunks y manifest RAG presentes.",
    )


def _consultation_runtime_capability(settings: Settings) -> RuntimeCapability:
    policy = Path(settings.legal_retrieval_policy_path).expanduser()
    rules = Path(settings.runtime_rule_set_path).expanduser()
    missing: list[str] = []
    if not policy.is_file():
        missing.append("legal_retrieval_policy")
    if not rules.is_file():
        missing.append("runtime_rule_set")
    if missing:
        return RuntimeCapability(
            name="consultation_runtime",
            available=False,
            detail="Configuración del runtime ausente: " + ", ".join(missing),
        )
    return RuntimeCapability(
        name="consultation_runtime",
        available=True,
        detail="Política jurídica y reglas del runtime disponibles.",
    )


def build_readiness_report(settings: Settings) -> ReadinessReport:
    capabilities = [
        _database_capability(),
        _rag_capability(settings),
        _consultation_runtime_capability(settings),
    ]
    database_ok = capabilities[0].available
    rag_ok = capabilities[1].available
    runtime_config_ok = capabilities[2].available

    if not database_ok:
        state = ReadinessState.NOT_READY
    elif settings.require_rag_artifacts and (not rag_ok or not runtime_config_ok):
        state = ReadinessState.NOT_READY
    elif not rag_ok or not runtime_config_ok:
        state = ReadinessState.DEGRADED
    else:
        state = ReadinessState.READY

    return ReadinessReport(
        state=state,
        platform=settings.deployment_platform,
        runtime_profile=settings.runtime_profile,
        capabilities=capabilities,
    )
