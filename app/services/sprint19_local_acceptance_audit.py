from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.services.normative_temporal_runtime_guard import (
    TemporalRuntimeGuardError,
    load_temporal_runtime_guard,
)
from rag.indexing.models import IndexManifest


class Sprint19LocalAcceptanceError(RuntimeError):
    """Fallo controlado de la auditoría local de cierre del Sprint 19."""


@dataclass(frozen=True)
class Sprint19LocalAcceptanceSummary:
    semantic_status: str
    semantic_parent_chunks: int
    semantic_document_count: int
    semantic_sha256: str
    runtime_chunk_count: int
    runtime_vector_dimension: int
    runtime_model_name: str
    runtime_index_sha256: str
    runtime_chunks_sha256: str
    temporal_schema_version: str
    temporal_blocked_documents: tuple[str, ...]
    temporal_entry_count: int
    temporal_coverage_gap_count: int
    default_runtime_dir: str
    failures: tuple[str, ...]


@dataclass(frozen=True)
class Sprint19LocalAcceptancePaths:
    semantic_corpus: Path
    semantic_manifest: Path
    runtime_dir: Path
    temporal_registry: Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise Sprint19LocalAcceptanceError(f"No se pudo leer {path}") from exc
    return digest.hexdigest()


def _json_object(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise Sprint19LocalAcceptanceError(f"No existe {label}: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Sprint19LocalAcceptanceError(f"JSON inválido en {label}: {path}") from exc
    if not isinstance(value, dict):
        raise Sprint19LocalAcceptanceError(f"{label} debe ser un objeto JSON.")
    return value


def _count_nonempty_lines(path: Path) -> int:
    if not path.is_file():
        raise Sprint19LocalAcceptanceError(f"No existe archivo JSONL: {path}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())
    except (OSError, UnicodeError) as exc:
        raise Sprint19LocalAcceptanceError(f"No se pudo contar {path}") from exc


def audit_sprint19_local_acceptance(
    *,
    paths: Sprint19LocalAcceptancePaths,
    expected_semantic_parents: int = 2981,
    expected_semantic_documents: int = 16,
    expected_runtime_chunks: int = 29326,
    expected_vector_dimension: int = 384,
    expected_model_name: str = (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    ),
    expected_blocked_documents: frozenset[str] = frozenset({"liva", "cpeum"}),
) -> Sprint19LocalAcceptanceSummary:
    semantic_manifest = _json_object(
        paths.semantic_manifest,
        label="manifiesto semántico",
    )
    failures: list[str] = []

    semantic_status = str(semantic_manifest.get("status", ""))
    semantic_parent_chunks = int(semantic_manifest.get("promoted_chunks", -1))
    semantic_document_count = int(semantic_manifest.get("document_count", -1))
    semantic_manifest_sha = str(semantic_manifest.get("promoted_sha256", ""))
    semantic_real_sha = _sha256(paths.semantic_corpus)
    semantic_real_count = _count_nonempty_lines(paths.semantic_corpus)

    if semantic_status != "approved_semantic_canonical":
        failures.append(f"semantic_status={semantic_status!r}")
    if semantic_parent_chunks != expected_semantic_parents:
        failures.append(
            "semantic_parent_chunks="
            f"{semantic_parent_chunks} esperado={expected_semantic_parents}"
        )
    if semantic_real_count != expected_semantic_parents:
        failures.append(
            f"semantic_real_count={semantic_real_count} esperado={expected_semantic_parents}"
        )
    if semantic_document_count != expected_semantic_documents:
        failures.append(
            "semantic_document_count="
            f"{semantic_document_count} esperado={expected_semantic_documents}"
        )
    if semantic_manifest_sha != semantic_real_sha:
        failures.append("semantic_sha256_mismatch")

    runtime_manifest_path = paths.runtime_dir / "manifest.json"
    runtime_index_path = paths.runtime_dir / "index.faiss"
    runtime_chunks_path = paths.runtime_dir / "chunks.jsonl"
    runtime_manifest_raw = _json_object(
        runtime_manifest_path,
        label="manifiesto runtime semántico",
    )
    try:
        runtime_manifest = IndexManifest.model_validate(runtime_manifest_raw)
    except ValueError as exc:
        raise Sprint19LocalAcceptanceError(
            f"Manifiesto runtime inválido: {runtime_manifest_path}"
        ) from exc

    if runtime_manifest.chunk_count != expected_runtime_chunks:
        failures.append(
            "runtime_chunk_count="
            f"{runtime_manifest.chunk_count} esperado={expected_runtime_chunks}"
        )
    if runtime_manifest.vector_dimension != expected_vector_dimension:
        failures.append(
            "runtime_vector_dimension="
            f"{runtime_manifest.vector_dimension} esperado={expected_vector_dimension}"
        )
    if runtime_manifest.model_name != expected_model_name:
        failures.append(
            f"runtime_model_name={runtime_manifest.model_name!r}"
        )
    if _count_nonempty_lines(runtime_chunks_path) != expected_runtime_chunks:
        failures.append("runtime_chunks_jsonl_count_mismatch")
    runtime_index_sha = _sha256(runtime_index_path)
    runtime_chunks_sha = _sha256(runtime_chunks_path)
    if runtime_index_sha != runtime_manifest.index_sha256:
        failures.append("runtime_index_sha256_mismatch")
    if runtime_chunks_sha != runtime_manifest.chunks_sha256:
        failures.append("runtime_chunks_sha256_mismatch")

    temporal_raw = _json_object(
        paths.temporal_registry,
        label="registro de procedencia temporal",
    )
    try:
        temporal_guard = load_temporal_runtime_guard(paths.temporal_registry)
    except TemporalRuntimeGuardError as exc:
        raise Sprint19LocalAcceptanceError(
            "Registro temporal inválido."
        ) from exc

    raw_entries = temporal_raw.get("entries")
    raw_gaps = temporal_raw.get("coverage_gaps")
    if not isinstance(raw_entries, list) or not isinstance(raw_gaps, list):
        raise Sprint19LocalAcceptanceError(
            "El registro temporal requiere entries y coverage_gaps como listas."
        )

    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict):
            failures.append("temporal_entry_invalid_type")
            continue
        if raw_entry.get("effective_from") is not None:
            failures.append("temporal_entry_effective_from_not_null")
        if raw_entry.get("effective_to") is not None:
            failures.append("temporal_entry_effective_to_not_null")
        if raw_entry.get("document_wide_applicable") is not False:
            failures.append("temporal_entry_document_wide_not_false")

    blocked = frozenset(temporal_guard.blocked_documents)
    if not expected_blocked_documents.issubset(blocked):
        failures.append(
            "temporal_blocked_documents="
            f"{sorted(blocked)} esperado_incluye={sorted(expected_blocked_documents)}"
        )

    default_runtime_dir = Settings().rag_artifact_dir
    if default_runtime_dir != "deployment/runtime_artifacts_semantic_v2":
        failures.append(f"default_runtime_dir={default_runtime_dir!r}")

    return Sprint19LocalAcceptanceSummary(
        semantic_status=semantic_status,
        semantic_parent_chunks=semantic_parent_chunks,
        semantic_document_count=semantic_document_count,
        semantic_sha256=semantic_real_sha,
        runtime_chunk_count=runtime_manifest.chunk_count,
        runtime_vector_dimension=runtime_manifest.vector_dimension,
        runtime_model_name=runtime_manifest.model_name,
        runtime_index_sha256=runtime_index_sha,
        runtime_chunks_sha256=runtime_chunks_sha,
        temporal_schema_version=temporal_guard.schema_version,
        temporal_blocked_documents=tuple(sorted(blocked)),
        temporal_entry_count=len(raw_entries),
        temporal_coverage_gap_count=len(raw_gaps),
        default_runtime_dir=default_runtime_dir,
        failures=tuple(failures),
    )


def summary_as_dict(summary: Sprint19LocalAcceptanceSummary) -> dict[str, object]:
    return asdict(summary)
