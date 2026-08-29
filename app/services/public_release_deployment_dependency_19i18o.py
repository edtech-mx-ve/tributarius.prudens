from __future__ import annotations

import hashlib
import json
import os
import tempfile
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

EXPECTED_CANDIDATE_SHA256 = (
    "4766b49014c5f40aa509b325ddb7268ca7032348559937d2ebae74b0dcefe360"
)
EXPECTED_CANONICAL_SHA256 = (
    "7b4bb564cdfbd849a961790bcfad938d09369ffc41edc2de4cedce1cab2c49b0"
)
DEFAULT_QUERY = "¿Cuáles son las obligaciones fiscales básicas de un contribuyente?"
MODEL_KEY_CANDIDATES = {
    "embedding_model",
    "embedding_model_id",
    "embedding_model_name",
    "model_name",
    "sentence_transformer_model",
    "sentence_transformers_model",
}


class DeploymentDependencyError(RuntimeError):
    """Fail-closed error for Sprint 19I.18O."""


@dataclass(frozen=True)
class SemanticProbe:
    model_id: str
    embedding_dimension: int
    faiss_dimension: int
    faiss_ntotal: int
    top_ids: tuple[int, ...]
    top_document_ids: tuple[str, ...]
    query_sha256: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DeploymentDependencyError(f"JSON inválido: {path}") from exc
    if not isinstance(value, dict):
        raise DeploymentDependencyError(f"Objeto JSON esperado: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def validate_upstream_19n(report_path: Path) -> dict[str, Any]:
    report = load_json(report_path)
    required = {
        "candidate_zip_sha256": EXPECTED_CANDIDATE_SHA256,
        "canonical_sha256": EXPECTED_CANONICAL_SHA256,
        "manifest_integrity_passed": True,
        "zip_path_safety_passed": True,
        "runtime_loaded_from_extracted_candidate_only": True,
        "source_runtime_path_not_used": True,
        "blocked_document_identity_absent": True,
        "cold_start_acceptance": True,
        "embedding_model_bundled": False,
        "embedding_model_external_dependency": True,
        "semantic_query_embedding_cold_start_proven": False,
        "deployment_sufficiency_acceptance": False,
        "public_release_allowed": False,
        "git_push_allowed": False,
        "github_release_allowed": False,
        "render_deploy_allowed": False,
    }
    mismatches = {
        key: (report.get(key), expected)
        for key, expected in required.items()
        if report.get(key) != expected
    }
    if mismatches:
        raise DeploymentDependencyError(
            f"19N no cumple precondiciones de 19O: {mismatches}"
        )
    return report


def _collect_model_ids(value: Any, parent_key: str = "") -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = key.casefold()
            if lowered in MODEL_KEY_CANDIDATES and isinstance(child, str):
                candidate = child.strip()
                if candidate:
                    found.add(candidate)
            found.update(_collect_model_ids(child, lowered))
    elif isinstance(value, list):
        for child in value:
            found.update(_collect_model_ids(child, parent_key))
    elif isinstance(value, str):
        text = value.strip()
        if "sentence-transformers/" in text:
            start = text.find("sentence-transformers/")
            token = text[start:].split()[0].strip("\"',;)]}")
            if token:
                found.add(token)
    return found


def resolve_embedding_model_id(runtime_dir: Path) -> str:
    candidates: set[str] = set()
    for path in sorted(runtime_dir.rglob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        candidates.update(_collect_model_ids(value))

    plausible = sorted(
        candidate
        for candidate in candidates
        if "/" in candidate and not candidate.startswith(("/", "\\"))
    )
    if len(plausible) != 1:
        raise DeploymentDependencyError(
            "No se pudo resolver un único modelo de embeddings desde el runtime; "
            f"candidatos={plausible}"
        )
    return plausible[0]


def load_chunks(chunks_path: Path) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    with chunks_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DeploymentDependencyError(
                    f"chunks.jsonl inválido en línea {line_number}"
                ) from exc
            if not isinstance(row, dict):
                raise DeploymentDependencyError(
                    f"Chunk inválido en línea {line_number}"
                )
            chunks.append(row)
    if not chunks:
        raise DeploymentDependencyError("Runtime sin chunks")
    return chunks


def find_single_faiss(runtime_dir: Path) -> Path:
    matches = sorted(runtime_dir.rglob("*.faiss"))
    if len(matches) != 1:
        raise DeploymentDependencyError(
            f"Se esperaba un único índice FAISS; encontrados={matches}"
        )
    return matches[0]


@contextmanager
def isolated_huggingface_environment(cache_root: Path) -> Iterator[None]:
    keys = {
        "HF_HOME": str(cache_root / "hf"),
        "HUGGINGFACE_HUB_CACHE": str(cache_root / "hf" / "hub"),
        "TRANSFORMERS_CACHE": str(cache_root / "transformers"),
        "SENTENCE_TRANSFORMERS_HOME": str(cache_root / "sentence_transformers"),
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
        "HF_TOKEN": "",
        "HUGGING_FACE_HUB_TOKEN": "",
    }
    previous = {key: os.environ.get(key) for key in keys}
    try:
        os.environ.update(keys)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def cache_size_bytes(path: Path) -> int:
    return sum(
        child.stat().st_size
        for child in path.rglob("*")
        if child.is_file()
    )


def _load_model(
    model_id: str,
    cache_root: Path,
    *,
    local_files_only: bool,
) -> SentenceTransformer:
    try:
        return SentenceTransformer(
            model_id,
            cache_folder=str(cache_root / "sentence_transformers"),
            local_files_only=local_files_only,
        )
    except Exception as exc:  # noqa: BLE001
        mode = "offline" if local_files_only else "online"
        raise DeploymentDependencyError(
            f"No se pudo cargar el modelo {model_id!r} en modo {mode}"
        ) from exc


def prefetch_and_verify_offline(
    model_id: str,
    cache_root: Path,
) -> SentenceTransformer:
    if cache_root.exists():
        raise DeploymentDependencyError(
            f"Cache 19O ya existe: {cache_root}; revisar antes de reintentar"
        )
    cache_root.mkdir(parents=True)

    with isolated_huggingface_environment(cache_root):
        _load_model(model_id, cache_root, local_files_only=False)
        if cache_size_bytes(cache_root) <= 0:
            raise DeploymentDependencyError(
                "La precarga del modelo no produjo archivos en cache aislada"
            )

        os.environ["HF_HUB_OFFLINE"] = "1"
        try:
            offline_model = _load_model(
                model_id,
                cache_root,
                local_files_only=True,
            )
        finally:
            os.environ.pop("HF_HUB_OFFLINE", None)

    return offline_model


def semantic_query_probe(
    *,
    runtime_dir: Path,
    model: SentenceTransformer,
    model_id: str,
    query: str,
    top_k: int = 3,
) -> SemanticProbe:
    chunks = load_chunks(runtime_dir / "chunks.jsonl")
    index_path = find_single_faiss(runtime_dir)
    try:
        index = faiss.read_index(str(index_path))
    except Exception as exc:  # noqa: BLE001
        raise DeploymentDependencyError("No se pudo cargar FAISS") from exc

    try:
        vector = model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
    except Exception as exc:  # noqa: BLE001
        raise DeploymentDependencyError(
            "El modelo no pudo vectorizar la consulta de smoke"
        ) from exc

    matrix = np.asarray(vector, dtype="float32")
    if matrix.ndim != 2 or matrix.shape[0] != 1:
        raise DeploymentDependencyError(
            f"Embedding con shape inesperado: {matrix.shape}"
        )
    if not np.isfinite(matrix).all():
        raise DeploymentDependencyError("Embedding contiene NaN/Inf")

    dimension = int(matrix.shape[1])
    if dimension != int(index.d):
        raise DeploymentDependencyError(
            f"Dimensión modelo/FAISS incompatible: {dimension} != {index.d}"
        )
    if int(index.ntotal) != len(chunks):
        raise DeploymentDependencyError(
            f"FAISS/chunks desalineados: {index.ntotal} != {len(chunks)}"
        )

    _distances, ids = index.search(matrix, min(top_k, int(index.ntotal)))
    top_ids = tuple(int(item) for item in ids[0] if int(item) >= 0)
    if not top_ids:
        raise DeploymentDependencyError("FAISS no devolvió resultados")

    document_ids: list[str] = []
    for item_id in top_ids:
        if not 0 <= item_id < len(chunks):
            raise DeploymentDependencyError(
                f"FAISS devolvió id fuera de rango: {item_id}"
            )
        metadata = chunks[item_id].get("metadata")
        if not isinstance(metadata, dict):
            raise DeploymentDependencyError(
                f"Metadata inválida para resultado {item_id}"
            )
        document_id = metadata.get("document_id")
        if not isinstance(document_id, str) or not document_id:
            raise DeploymentDependencyError(
                f"document_id inválido para resultado {item_id}"
            )
        document_ids.append(document_id)

    return SemanticProbe(
        model_id=model_id,
        embedding_dimension=dimension,
        faiss_dimension=int(index.d),
        faiss_ntotal=int(index.ntotal),
        top_ids=top_ids,
        top_document_ids=tuple(document_ids),
        query_sha256=hashlib.sha256(query.encode("utf-8")).hexdigest(),
    )


def execute(
    *,
    candidate_zip: Path,
    report_19n: Path,
    output_dir: Path,
) -> dict[str, Any]:
    if output_dir.exists():
        raise DeploymentDependencyError(
            f"Output ya existe: {output_dir}; revisar antes de reintentar"
        )
    if sha256_file(candidate_zip) != EXPECTED_CANDIDATE_SHA256:
        raise DeploymentDependencyError("Candidato 19M no coincide con SHA aprobado")

    validate_upstream_19n(report_19n)

    with tempfile.TemporaryDirectory(prefix="tributarius_19o_") as temp_name:
        extracted = Path(temp_name) / "candidate"
        with zipfile.ZipFile(candidate_zip, "r") as archive:
            archive.extractall(extracted)

        runtime_dir = extracted / "runtime"
        if not runtime_dir.is_dir():
            raise DeploymentDependencyError("Runtime ausente en candidato extraído")

        model_id = resolve_embedding_model_id(runtime_dir)

        output_dir.mkdir(parents=True)
        cache_root = output_dir / "embedding_cache"
        model = prefetch_and_verify_offline(model_id, cache_root)
        probe = semantic_query_probe(
            runtime_dir=runtime_dir,
            model=model,
            model_id=model_id,
            query=DEFAULT_QUERY,
        )

    report = {
        "sprint": "19I.18O",
        "status": "external_embedding_dependency_closed_locally",
        "candidate_zip_sha256": EXPECTED_CANDIDATE_SHA256,
        "canonical_sha256": EXPECTED_CANONICAL_SHA256,
        "model_id": probe.model_id,
        "fresh_unauthenticated_model_fetch_passed": True,
        "isolated_model_cache_created": True,
        "isolated_model_cache_bytes": cache_size_bytes(
            output_dir / "embedding_cache"
        ),
        "offline_model_reload_passed": True,
        "semantic_query_embedding_cold_start_proven": True,
        "embedding_dimension": probe.embedding_dimension,
        "faiss_dimension": probe.faiss_dimension,
        "faiss_ntotal": probe.faiss_ntotal,
        "semantic_probe_top_ids": list(probe.top_ids),
        "semantic_probe_top_document_ids": list(probe.top_document_ids),
        "semantic_probe_query_sha256": probe.query_sha256,
        "runtime_loaded_from_candidate_only": True,
        "source_corpus_not_used": True,
        "commercial_api_required": False,
        "api_key_required": False,
        "credit_card_required": False,
        "deployment_sufficiency_acceptance": True,
        "model_weights_in_public_candidate": False,
        "model_cache_local_build_artifact_only": True,
        "model_license_review_required": True,
        "publication_legal_acceptance": False,
        "temporal_validity_complete": False,
        "redistribution_human_review_required": True,
        "public_release_allowed": False,
        "git_push_allowed": False,
        "github_release_allowed": False,
        "render_deploy_allowed": False,
        "automatic_publication_performed": False,
    }
    write_json(output_dir / "deployment_dependency_acceptance.json", report)
    return report
