from __future__ import annotations

import hashlib
import json
import math
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import faiss
import numpy as np

EXPECTED_CANDIDATE_SHA256 = (
    "18ac85d3b2612a3057dd6e24660487457af078eb8abdf2bb94e122c9bc97c514"
)
EXPECTED_CANONICAL_SHA256 = (
    "7b4bb564cdfbd849a961790bcfad938d09369ffc41edc2de4cedce1cab2c49b0"
)
EXPECTED_PARENT_COUNT = 2962

ALLOWED_NORMATIVE_DOCUMENTS = {
    "cff",
    "cpeum",
    "lfdc",
    "lfisan",
    "lfpca",
    "lieps",
    "lif_2026",
    "lisr",
    "liva",
    "lotfja",
    "reg_cff",
    "reg_lisr_060516",
    "reg_liva_250914",
    "rmf_2026",
}
BLOCKED_DOCUMENTS = {
    "manual_unam",
    "manual_derecho_fiscal_unam",
    "prodecon",
    "prodecon_contribuyente",
}
FORBIDDEN_SUFFIXES = {
    ".pdf",
    ".md",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pem",
    ".key",
    ".safetensors",
    ".pt",
    ".pth",
    ".onnx",
}


class ColdStartError(RuntimeError):
    """Fail-closed error for Sprint 19I.18N."""


@dataclass(frozen=True)
class RuntimeProbe:
    chunk_count: int
    unique_document_count: int
    document_ids: tuple[str, ...]
    faiss_ntotal: int
    faiss_dimension: int
    probe_top1_id: int
    probe_distance: float


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
        raise ColdStartError(f"JSON invÃ¡lido: {path}") from exc
    if not isinstance(value, dict):
        raise ColdStartError(f"Objeto JSON esperado: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def validate_zip_member_name(name: str) -> None:
    if not name or name.endswith("/"):
        return
    normalized = name.replace("\\", "/")
    posix = PurePosixPath(normalized)
    if posix.is_absolute():
        raise ColdStartError(f"Ruta absoluta en ZIP: {name}")
    if ".." in posix.parts:
        raise ColdStartError(f"Path traversal en ZIP: {name}")
    if len(posix.parts) == 0:
        raise ColdStartError(f"Entrada ZIP invÃ¡lida: {name}")
    if posix.parts[0] not in {
        "runtime",
        "release_metadata.json",
        "release_manifest.json",
    }:
        raise ColdStartError(f"Entrada fuera del contrato del bundle: {name}")
    if Path(normalized).suffix.casefold() in FORBIDDEN_SUFFIXES:
        raise ColdStartError(f"ExtensiÃ³n prohibida en candidato: {name}")


def validate_candidate_zip(candidate_zip: Path) -> list[str]:
    if not candidate_zip.is_file():
        raise ColdStartError(f"Candidato ausente: {candidate_zip}")
    actual_sha = sha256_file(candidate_zip)
    if actual_sha != EXPECTED_CANDIDATE_SHA256:
        raise ColdStartError(
            "SHA del candidato 19M inesperado: "
            f"{actual_sha}; esperado={EXPECTED_CANDIDATE_SHA256}"
        )

    try:
        with zipfile.ZipFile(candidate_zip, "r") as archive:
            names = archive.namelist()
            if not names:
                raise ColdStartError("ZIP candidato vacÃo")
            seen: set[str] = set()
            for info in archive.infolist():
                validate_zip_member_name(info.filename)
                normalized = info.filename.replace("\\", "/")
                if normalized in seen:
                    raise ColdStartError(f"Entrada ZIP duplicada: {normalized}")
                seen.add(normalized)

                unix_mode = (info.external_attr >> 16) & 0o170000
                if unix_mode == 0o120000:
                    raise ColdStartError(f"Symlink no permitido en ZIP: {normalized}")
    except zipfile.BadZipFile as exc:
        raise ColdStartError("Candidato ZIP corrupto") from exc
    return sorted(name.replace("\\", "/") for name in names if not name.endswith("/"))


def extract_candidate(candidate_zip: Path, destination: Path) -> None:
    if destination.exists():
        raise ColdStartError(
            f"Destino ya existe: {destination}; revisar antes de reintentar"
        )
    destination.mkdir(parents=True)
    with zipfile.ZipFile(candidate_zip, "r") as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            validate_zip_member_name(info.filename)
            relative = PurePosixPath(info.filename.replace("\\", "/"))
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)


def verify_release_contract(extracted: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata = load_json(extracted / "release_metadata.json")
    manifest = load_json(extracted / "release_manifest.json")

    required_metadata = {
        "candidate_only": True,
        "canonical_sha256": EXPECTED_CANONICAL_SHA256,
        "parent_count": EXPECTED_PARENT_COUNT,
        "normative_document_count": 14,
        "benchmark_passed": True,
        "blocked_content_absent": True,
        "provenance_complete": True,
        "temporal_fail_closed_complete": True,
        "temporal_validity_complete": False,
        "redistribution_human_review_required": True,
        "publication_legal_acceptance": False,
        "public_release_allowed": False,
        "git_push_allowed": False,
        "github_release_allowed": False,
        "render_deploy_allowed": False,
        "automatic_publication_performed": False,
    }
    mismatches = {
        key: (metadata.get(key), expected)
        for key, expected in required_metadata.items()
        if metadata.get(key) != expected
    }
    if mismatches:
        raise ColdStartError(f"Contrato release_metadata divergente: {mismatches}")

    if manifest.get("candidate_only") is not True:
        raise ColdStartError("Manifest no marcado candidate_only")
    if manifest.get("canonical_sha256") != EXPECTED_CANONICAL_SHA256:
        raise ColdStartError("Manifest referencia canonical inesperado")

    raw_files = manifest.get("files")
    if not isinstance(raw_files, list) or not raw_files:
        raise ColdStartError("Manifest sin lista de archivos")

    expected_paths: set[str] = set()
    for item in raw_files:
        if not isinstance(item, dict):
            raise ColdStartError("Entrada invÃ¡lida en release_manifest.files")
        rel = item.get("path")
        size = item.get("size")
        digest = item.get("sha256")
        if not isinstance(rel, str) or not isinstance(size, int) or not isinstance(digest, str):
            raise ColdStartError("Manifest con tipos invÃ¡lidos")
        if rel in expected_paths:
            raise ColdStartError(f"Ruta duplicada en manifest: {rel}")
        expected_paths.add(rel)

        target = extracted.joinpath(*PurePosixPath(rel).parts)
        if not target.is_file():
            raise ColdStartError(f"Archivo manifestado ausente: {rel}")
        if target.stat().st_size != size:
            raise ColdStartError(f"TamaÃ±o divergente: {rel}")
        if sha256_file(target) != digest:
            raise ColdStartError(f"SHA divergente: {rel}")

    actual_paths = {
        path.relative_to(extracted).as_posix()
        for path in extracted.rglob("*")
        if path.is_file() and path.name != "release_manifest.json"
    }
    if actual_paths != expected_paths:
        missing = sorted(expected_paths - actual_paths)
        extra = sorted(actual_paths - expected_paths)
        raise ColdStartError(
            f"Contenido extra/ausente respecto al manifest; missing={missing}; extra={extra}"
        )

    return metadata, manifest


def load_chunks(chunks_path: Path) -> tuple[list[dict[str, Any]], set[str]]:
    chunks: list[dict[str, Any]] = []
    document_ids: set[str] = set()

    if not chunks_path.is_file():
        raise ColdStartError(f"chunks.jsonl ausente: {chunks_path}")

    with chunks_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ColdStartError(
                    f"chunks.jsonl invÃ¡lido en lÃnea {line_number}"
                ) from exc
            if not isinstance(chunk, dict):
                raise ColdStartError(
                    f"Chunk no es objeto en lÃnea {line_number}"
                )
            chunk_id = chunk.get("chunk_id")
            metadata = chunk.get("metadata")
            if not isinstance(chunk_id, str) or not chunk_id:
                raise ColdStartError(
                    f"chunk_id invÃ¡lido en lÃnea {line_number}"
                )
            if not isinstance(metadata, dict):
                raise ColdStartError(
                    f"metadata invÃ¡lida en lÃnea {line_number}"
                )
            document_id = metadata.get("document_id")
            if not isinstance(document_id, str):
                raise ColdStartError(
                    f"document_id invÃ¡lido en lÃnea {line_number}"
                )
            if document_id in BLOCKED_DOCUMENTS:
                raise ColdStartError(
                    f"Documento bloqueado encontrado: {document_id}"
                )
            if document_id not in ALLOWED_NORMATIVE_DOCUMENTS:
                raise ColdStartError(
                    f"Documento fuera del scope normativo: {document_id}"
                )
            text = chunk.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ColdStartError(
                    f"Texto vacÃo/invÃ¡lido en lÃnea {line_number}"
                )
            chunks.append(chunk)
            document_ids.add(document_id)

    if not chunks:
        raise ColdStartError("Runtime sin chunks")
    if document_ids != ALLOWED_NORMATIVE_DOCUMENTS:
        missing = sorted(ALLOWED_NORMATIVE_DOCUMENTS - document_ids)
        extra = sorted(document_ids - ALLOWED_NORMATIVE_DOCUMENTS)
        raise ColdStartError(
            f"Cobertura documental runtime divergente; missing={missing}; extra={extra}"
        )
    return chunks, document_ids


def find_single_runtime_file(runtime_dir: Path, suffix: str) -> Path:
    matches = sorted(
        path for path in runtime_dir.rglob(f"*{suffix}") if path.is_file()
    )
    if len(matches) != 1:
        raise ColdStartError(
            f"Se esperaba exactamente un archivo {suffix}; encontrados={matches}"
        )
    return matches[0]


def probe_faiss(index_path: Path, chunk_count: int) -> tuple[int, int, int, float]:
    try:
        index = faiss.read_index(str(index_path))
    except Exception as exc:  # noqa: BLE001
        raise ColdStartError(f"No se pudo cargar FAISS: {index_path}") from exc

    ntotal = int(index.ntotal)
    dimension = int(index.d)
    if ntotal <= 0 or dimension <= 0:
        raise ColdStartError(
            f"Ãndice FAISS invÃ¡lido: ntotal={ntotal}, d={dimension}"
        )
    if ntotal != chunk_count:
        raise ColdStartError(
            f"DesalineaciÃ³n FAISS/chunks: ntotal={ntotal}, chunks={chunk_count}"
        )

    try:
        vector = np.asarray(index.reconstruct(0), dtype="float32").reshape(1, -1)
    except Exception as exc:  # noqa: BLE001
        raise ColdStartError(
            "El Ãndice no permite reconstruir un vector para el smoke aislado"
        ) from exc

    if vector.shape != (1, dimension):
        raise ColdStartError(
            f"Vector reconstruido con dimensiÃ³n inesperada: {vector.shape}"
        )
    if not np.isfinite(vector).all():
        raise ColdStartError("Vector de prueba contiene NaN/Inf")

    distances, ids = index.search(vector, min(3, ntotal))
    top1 = int(ids[0, 0])
    distance = float(distances[0, 0])
    if not 0 <= top1 < ntotal:
        raise ColdStartError(f"FAISS devolviÃ³ id fuera de rango: {top1}")
    if not math.isfinite(distance):
        raise ColdStartError("FAISS devolviÃ³ distancia no finita")
    return ntotal, dimension, top1, distance


def run_runtime_probe(extracted: Path) -> RuntimeProbe:
    runtime = extracted / "runtime"
    if not runtime.is_dir():
        raise ColdStartError("Directorio runtime ausente")

    chunks_path = runtime / "chunks.jsonl"
    chunks, document_ids = load_chunks(chunks_path)
    index_path = find_single_runtime_file(runtime, ".faiss")
    ntotal, dimension, top1, distance = probe_faiss(index_path, len(chunks))

    return RuntimeProbe(
        chunk_count=len(chunks),
        unique_document_count=len(document_ids),
        document_ids=tuple(sorted(document_ids)),
        faiss_ntotal=ntotal,
        faiss_dimension=dimension,
        probe_top1_id=top1,
        probe_distance=distance,
    )


def audit_deployment_sufficiency(extracted: Path) -> dict[str, Any]:
    runtime = extracted / "runtime"
    model_weight_files = [
        path
        for path in runtime.rglob("*")
        if path.is_file()
        and path.suffix.casefold()
        in {".safetensors", ".pt", ".pth", ".onnx", ".bin"}
    ]
    embedding_model_bundled = bool(model_weight_files)
    return {
        "candidate_runtime_present": runtime.is_dir(),
        "embedding_model_bundled": embedding_model_bundled,
        "embedding_model_external_dependency": not embedding_model_bundled,
        "semantic_query_embedding_cold_start_proven": False,
        "semantic_query_embedding_cold_start_reason": (
            "El bundle pÃºblico 19M excluye pesos de modelo por diseÃ±o; "
            "19N prueba el runtime FAISS/chunks en aislamiento, no la descarga "
            "o disponibilidad externa del Sentence Transformer."
        ),
    }


def execute(
    *,
    candidate_zip: Path,
    output_dir: Path,
) -> dict[str, Any]:
    if output_dir.exists():
        raise ColdStartError(
            f"Output ya existe: {output_dir}; revisar antes de reintentar"
        )

    zip_members = validate_candidate_zip(candidate_zip)
    extracted = output_dir / "isolated"
    extract_candidate(candidate_zip, extracted)

    metadata, _manifest = verify_release_contract(extracted)
    probe = run_runtime_probe(extracted)
    sufficiency = audit_deployment_sufficiency(extracted)

    cold_start_acceptance = (
        probe.chunk_count == probe.faiss_ntotal
        and probe.unique_document_count == 14
        and metadata.get("candidate_only") is True
    )
    if not cold_start_acceptance:
        raise ColdStartError("Cold-start no cumple criterios mÃnimos")

    deployment_sufficiency_acceptance = bool(
        cold_start_acceptance
        and sufficiency["embedding_model_bundled"]
        and sufficiency["semantic_query_embedding_cold_start_proven"]
    )

    report = {
        "sprint": "19I.18N",
        "status": "local_isolated_cold_start_validated",
        "candidate_zip_sha256": sha256_file(candidate_zip),
        "candidate_zip_member_count": len(zip_members),
        "canonical_sha256": EXPECTED_CANONICAL_SHA256,
        "parent_count": EXPECTED_PARENT_COUNT,
        "chunk_count": probe.chunk_count,
        "unique_document_count": probe.unique_document_count,
        "document_ids": list(probe.document_ids),
        "faiss_ntotal": probe.faiss_ntotal,
        "faiss_dimension": probe.faiss_dimension,
        "faiss_probe_top1_id": probe.probe_top1_id,
        "faiss_probe_distance": probe.probe_distance,
        "manifest_integrity_passed": True,
        "zip_path_safety_passed": True,
        "runtime_loaded_from_extracted_candidate_only": True,
        "source_runtime_path_not_used": True,
        "blocked_document_identity_absent": True,
        "cold_start_acceptance": cold_start_acceptance,
        **sufficiency,
        "deployment_sufficiency_acceptance": deployment_sufficiency_acceptance,
        "publication_legal_acceptance": False,
        "temporal_validity_complete": False,
        "redistribution_human_review_required": True,
        "public_release_allowed": False,
        "git_push_allowed": False,
        "github_release_allowed": False,
        "render_deploy_allowed": False,
        "automatic_publication_performed": False,
    }
    write_json(output_dir / "cold_start_acceptance.json", report)
    return report
