from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class RuntimeInnerIntegrityError(RuntimeError):
    """Fallo controlado de integridad del runtime RAG extraído."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeInnerIntegrityError("manifest.json interno inválido.") from exc
    if not isinstance(value, dict):
        raise RuntimeInnerIntegrityError("manifest.json interno debe ser objeto.")
    return value


def _count_jsonl(path: Path) -> int:
    count = 0
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise RuntimeInnerIntegrityError(
                        f"chunks.jsonl inválido en línea {line_number}."
                    ) from exc
                if not isinstance(item, dict):
                    raise RuntimeInnerIntegrityError(
                        f"Chunk no es objeto JSON en línea {line_number}."
                    )
                count += 1
    except (OSError, UnicodeError) as exc:
        raise RuntimeInnerIntegrityError("No se pudo leer chunks.jsonl.") from exc
    return count


def validate_runtime_inner_integrity(runtime_dir: Path) -> dict[str, int | str]:
    """Valida los invariantes internos que consume FaissRetriever.

    No confía únicamente en el release_manifest exterior.
    """
    runtime = runtime_dir.expanduser().resolve()
    manifest_path = runtime / "manifest.json"
    chunks_path = runtime / "chunks.jsonl"
    index_path = runtime / "index.faiss"
    for path in (manifest_path, chunks_path, index_path):
        if not path.is_file():
            raise RuntimeInnerIntegrityError(f"Falta artefacto runtime: {path.name}")

    manifest = _load_manifest(manifest_path)
    chunks_sha = _sha256(chunks_path)
    index_sha = _sha256(index_path)
    chunks_size = chunks_path.stat().st_size
    index_size = index_path.stat().st_size
    chunk_count = _count_jsonl(chunks_path)

    checks = (
        (str(manifest.get("chunks_sha256", "")).lower() == chunks_sha,
         "SHA-256 interno de chunks.jsonl divergente."),
        (str(manifest.get("index_sha256", "")).lower() == index_sha,
         "SHA-256 interno de index.faiss divergente."),
        (int(manifest.get("chunks_bytes", -1)) == chunks_size,
         "Tamaño interno de chunks.jsonl divergente."),
        (int(manifest.get("index_bytes", -1)) == index_size,
         "Tamaño interno de index.faiss divergente."),
        (int(manifest.get("chunk_count", -1)) == chunk_count,
         "Cardinalidad interna de chunks.jsonl divergente."),
    )
    for valid, message in checks:
        if not valid:
            raise RuntimeInnerIntegrityError(message)

    return {
        "chunk_count": chunk_count,
        "chunks_sha256": chunks_sha,
        "index_sha256": index_sha,
        "chunks_bytes": chunks_size,
        "index_bytes": index_size,
        "vector_dimension": int(manifest.get("vector_dimension", -1)),
    }
