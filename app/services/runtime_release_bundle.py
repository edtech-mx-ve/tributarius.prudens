from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from app.services.normative_temporal_runtime_guard import (
    TemporalRuntimeGuardError,
    load_temporal_runtime_guard,
)
from rag.indexing.models import IndexManifest


class RuntimeReleaseBundleError(RuntimeError):
    """Fallo controlado al construir o validar el bundle runtime."""


_RUNTIME_FILES: Final[tuple[str, ...]] = (
    "index.faiss",
    "chunks.jsonl",
    "manifest.json",
)
_FIXED_ZIP_DATETIME: Final[tuple[int, int, int, int, int, int]] = (
    2026,
    1,
    1,
    0,
    0,
    0,
)


@dataclass(frozen=True)
class RuntimeReleaseBundleSummary:
    output_path: str
    bundle_sha256: str
    bundle_size_bytes: int
    runtime_chunk_count: int
    runtime_vector_dimension: int
    runtime_model_name: str
    temporal_schema_version: str
    temporal_blocked_documents: tuple[str, ...]
    packaged_files: tuple[str, ...]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise RuntimeReleaseBundleError(f"No se pudo leer {path}") from exc
    return digest.hexdigest()


def _read_bytes(path: Path, *, label: str) -> bytes:
    if not path.is_file():
        raise RuntimeReleaseBundleError(f"No existe {label}: {path}")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise RuntimeReleaseBundleError(f"No se pudo leer {label}: {path}") from exc


def _load_runtime_manifest(path: Path) -> IndexManifest:
    raw = _read_bytes(path, label="manifest runtime")
    try:
        payload = json.loads(raw.decode("utf-8"))
        return IndexManifest.model_validate(payload)
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise RuntimeReleaseBundleError("Manifest runtime inválido.") from exc


def _validate_runtime_files(runtime_dir: Path) -> IndexManifest:
    manifest_path = runtime_dir / "manifest.json"
    manifest = _load_runtime_manifest(manifest_path)
    index_path = runtime_dir / manifest.index_filename
    chunks_path = runtime_dir / manifest.chunks_filename

    if _sha256_path(index_path) != manifest.index_sha256:
        raise RuntimeReleaseBundleError("SHA-256 de index.faiss no coincide con manifest.")
    if _sha256_path(chunks_path) != manifest.chunks_sha256:
        raise RuntimeReleaseBundleError("SHA-256 de chunks.jsonl no coincide con manifest.")

    return manifest


def _zip_write_bytes(
    archive: zipfile.ZipFile,
    *,
    arcname: str,
    data: bytes,
) -> None:
    info = zipfile.ZipInfo(filename=arcname, date_time=_FIXED_ZIP_DATETIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, data)


def build_runtime_release_bundle(
    *,
    runtime_dir: Path,
    temporal_registry: Path,
    output_path: Path,
) -> RuntimeReleaseBundleSummary:
    manifest = _validate_runtime_files(runtime_dir)

    try:
        temporal_guard = load_temporal_runtime_guard(temporal_registry)
    except TemporalRuntimeGuardError as exc:
        raise RuntimeReleaseBundleError("Registro temporal inválido.") from exc

    runtime_payloads: dict[str, bytes] = {}
    for filename in _RUNTIME_FILES:
        runtime_payloads[
            f"deployment/runtime_artifacts_semantic_v2/{filename}"
        ] = _read_bytes(runtime_dir / filename, label=filename)

    temporal_arcname = "knowledge/temporal/temporal_provenance_registry.json"
    temporal_payload = _read_bytes(
        temporal_registry,
        label="registro temporal",
    )

    file_hashes = {
        arcname: {
            "sha256": _sha256_bytes(payload),
            "size_bytes": len(payload),
        }
        for arcname, payload in sorted(
            {
                **runtime_payloads,
                temporal_arcname: temporal_payload,
            }.items()
        )
    }

    release_manifest = {
        "schema_version": "1.0",
        "artifact": "tributarius-prudens-runtime-semantic-v2",
        "runtime_dir": "deployment/runtime_artifacts_semantic_v2",
        "runtime_chunk_count": manifest.chunk_count,
        "runtime_vector_dimension": manifest.vector_dimension,
        "runtime_model_name": manifest.model_name,
        "temporal_registry": temporal_arcname,
        "temporal_schema_version": temporal_guard.schema_version,
        "temporal_blocked_documents": sorted(temporal_guard.blocked_documents),
        "files": file_hashes,
    }
    release_manifest_bytes = (
        json.dumps(
            release_manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")

    resolved_output = output_path.expanduser().resolve()
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    temporary = resolved_output.with_suffix(resolved_output.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()

    try:
        with zipfile.ZipFile(
            temporary,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for arcname, payload in sorted(runtime_payloads.items()):
                _zip_write_bytes(archive, arcname=arcname, data=payload)
            _zip_write_bytes(
                archive,
                arcname=temporal_arcname,
                data=temporal_payload,
            )
            _zip_write_bytes(
                archive,
                arcname="release_manifest.json",
                data=release_manifest_bytes,
            )
        temporary.replace(resolved_output)
    except OSError as exc:
        if temporary.exists():
            temporary.unlink()
        raise RuntimeReleaseBundleError("No se pudo escribir el bundle runtime.") from exc

    packaged_files = tuple(sorted((*runtime_payloads, temporal_arcname, "release_manifest.json")))
    return RuntimeReleaseBundleSummary(
        output_path=str(resolved_output),
        bundle_sha256=_sha256_path(resolved_output),
        bundle_size_bytes=resolved_output.stat().st_size,
        runtime_chunk_count=manifest.chunk_count,
        runtime_vector_dimension=manifest.vector_dimension,
        runtime_model_name=manifest.model_name,
        temporal_schema_version=temporal_guard.schema_version,
        temporal_blocked_documents=tuple(sorted(temporal_guard.blocked_documents)),
        packaged_files=packaged_files,
    )


def validate_runtime_release_bundle(path: Path) -> RuntimeReleaseBundleSummary:
    if not path.is_file():
        raise RuntimeReleaseBundleError(f"No existe bundle: {path}")

    try:
        with zipfile.ZipFile(path, mode="r") as archive:
            names = set(archive.namelist())
            if "release_manifest.json" not in names:
                raise RuntimeReleaseBundleError("Falta release_manifest.json.")
            release_manifest = json.loads(
                archive.read("release_manifest.json").decode("utf-8")
            )
            if not isinstance(release_manifest, dict):
                raise RuntimeReleaseBundleError("release_manifest debe ser objeto.")
            files = release_manifest.get("files")
            if not isinstance(files, dict):
                raise RuntimeReleaseBundleError("release_manifest.files inválido.")

            for arcname, metadata in files.items():
                if not isinstance(arcname, str) or not isinstance(metadata, dict):
                    raise RuntimeReleaseBundleError("Entrada de archivo inválida.")
                if arcname not in names:
                    raise RuntimeReleaseBundleError(f"Falta archivo: {arcname}")
                payload = archive.read(arcname)
                if _sha256_bytes(payload) != metadata.get("sha256"):
                    raise RuntimeReleaseBundleError(
                        f"SHA-256 interno inválido: {arcname}"
                    )
                if len(payload) != metadata.get("size_bytes"):
                    raise RuntimeReleaseBundleError(
                        f"Tamaño interno inválido: {arcname}"
                    )

            blocked_raw = release_manifest.get("temporal_blocked_documents", [])
            if not isinstance(blocked_raw, list) or not all(
                isinstance(item, str) for item in blocked_raw
            ):
                raise RuntimeReleaseBundleError(
                    "temporal_blocked_documents inválido."
                )

            return RuntimeReleaseBundleSummary(
                output_path=str(path.expanduser().resolve()),
                bundle_sha256=_sha256_path(path),
                bundle_size_bytes=path.stat().st_size,
                runtime_chunk_count=int(
                    release_manifest.get("runtime_chunk_count", -1)
                ),
                runtime_vector_dimension=int(
                    release_manifest.get("runtime_vector_dimension", -1)
                ),
                runtime_model_name=str(
                    release_manifest.get("runtime_model_name", "")
                ),
                temporal_schema_version=str(
                    release_manifest.get("temporal_schema_version", "")
                ),
                temporal_blocked_documents=tuple(sorted(blocked_raw)),
                packaged_files=tuple(sorted((*files.keys(), "release_manifest.json"))),
            )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        zipfile.BadZipFile,
    ) as exc:
        raise RuntimeReleaseBundleError("Bundle runtime inválido.") from exc
