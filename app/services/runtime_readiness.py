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


def build_readiness_report(settings: Settings) -> ReadinessReport:
    capabilities = [_database_capability(), _rag_capability(settings)]
    database_ok = capabilities[0].available
    rag_ok = capabilities[1].available

    if not database_ok:
        state = ReadinessState.NOT_READY
    elif settings.require_rag_artifacts and not rag_ok:
        state = ReadinessState.NOT_READY
    elif not rag_ok:
        state = ReadinessState.DEGRADED
    else:
        state = ReadinessState.READY

    return ReadinessReport(
        state=state,
        platform=settings.deployment_platform,
        runtime_profile=settings.runtime_profile,
        capabilities=capabilities,
    )
