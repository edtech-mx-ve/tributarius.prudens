from __future__ import annotations

import hashlib
import logging
import os
import tempfile
import time
import tracemalloc
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from app.domain.chunks import LegalChunk
from app.domain.legal_chunks import LegalChunk as CorpusLegalChunk
from rag.embeddings.provider import (
    DEFAULT_EMBEDDING_MODEL,
    EmbeddingError,
    EmbeddingProvider,
    SentenceTransformerEmbedder,
    normalize_rows,
)
from rag.indexing.faiss_store import FaissStoreError, FaissVectorStore
from rag.indexing.models import IndexManifest
from rag.indexing.runtime_adapter import adapt_corpus_chunk

logger = logging.getLogger(__name__)


class IndexBuildError(RuntimeError):
    """Error controlado durante la construcción del índice vectorial."""


class VectorStoreWriter(Protocol):
    def write(self, vectors: object, path: Path) -> Path:
        ...


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_chunk_line(line: str, *, line_number: int) -> LegalChunk:
    try:
        return LegalChunk.model_validate_json(line)
    except ValidationError:
        try:
            corpus_chunk = CorpusLegalChunk.model_validate_json(line)
        except ValidationError as exc:
            raise IndexBuildError(
                f"Chunk inválido en línea {line_number}: no coincide "
                "con el esquema runtime ni con Sprint 19C."
            ) from exc
        return adapt_corpus_chunk(corpus_chunk, chunk_index=line_number - 1)


def load_chunks_jsonl(path: Path) -> list[LegalChunk]:
    resolved = path.expanduser().resolve()
    if not resolved.exists() or not resolved.is_file():
        raise IndexBuildError(f"No existe el archivo de chunks: {resolved}")
    if resolved.suffix.lower() != ".jsonl":
        raise IndexBuildError("Los chunks deben estar en formato JSONL.")

    chunks: list[LegalChunk] = []
    try:
        with resolved.open("r", encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                chunks.append(_load_chunk_line(line, line_number=line_number))
    except OSError as exc:
        raise IndexBuildError(f"No fue posible leer {resolved}.") from exc

    if not chunks:
        raise IndexBuildError(f"El archivo no contiene chunks válidos: {resolved}")

    return chunks


def render_embedding_text(chunk: LegalChunk) -> str:
    hierarchy = chunk.metadata.hierarchy
    context = [
        f"Fuente: {chunk.metadata.source_type.value}",
        f"Documento: {chunk.metadata.title or chunk.metadata.source_filename}",
    ]

    # Los subchunks 19F conservan toda la metadata en JSON, pero usan un
    # encabezado compacto para no consumir el límite de 128 tokens con
    # información repetida antes de llegar al texto jurídico.
    if chunk.metadata.parent_chunk_id is not None:
        if chunk.metadata.source_unit_label:
            context.append(f"Unidad: {chunk.metadata.source_unit_label}")
        elif chunk.metadata.legal_identifier:
            context.append(f"Unidad: {chunk.metadata.legal_identifier}")
        context.append(f"Texto: {chunk.text}")
        return "\n".join(context)

    if chunk.metadata.source_role:
        context.append(f"Rol: {chunk.metadata.source_role}")
    if chunk.metadata.document_type:
        context.append(f"Tipo documental: {chunk.metadata.document_type}")
    if chunk.metadata.matter:
        context.append(f"Materia: {', '.join(chunk.metadata.matter)}")
    if chunk.metadata.source_unit_label:
        context.append(f"Unidad: {chunk.metadata.source_unit_label}")
    if hierarchy.title:
        context.append(f"Título: {hierarchy.title}")
    if hierarchy.chapter:
        context.append(f"Capítulo: {hierarchy.chapter}")
    if hierarchy.section:
        context.append(f"Sección: {hierarchy.section}")
    if hierarchy.article:
        context.append(f"Artículo: {hierarchy.article}")
    if hierarchy.fraction:
        context.append(f"Fracción: {hierarchy.fraction}")
    if hierarchy.subsection:
        context.append(f"Inciso: {hierarchy.subsection}")

    context.append(f"Texto: {chunk.text}")
    return "\n".join(context)


def _validate_unique_chunk_ids(chunks: Sequence[LegalChunk]) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for chunk in chunks:
        if chunk.chunk_id in seen and chunk.chunk_id not in duplicates:
            duplicates.append(chunk.chunk_id)
        seen.add(chunk.chunk_id)
    if duplicates:
        preview = ", ".join(sorted(duplicates)[:3])
        raise IndexBuildError(f"Se detectaron chunk_id duplicados: {preview}")


def _write_chunks(chunks: Sequence[LegalChunk], path: Path) -> None:
    payload = "\n".join(chunk.model_dump_json(exclude_none=True) for chunk in chunks)
    path.write_text(payload + "\n", encoding="utf-8")


def _safe_output_directory(output_dir: Path, *, overwrite: bool) -> Path:
    resolved = output_dir.expanduser().resolve()
    if resolved.exists() and not resolved.is_dir():
        raise IndexBuildError(f"La salida no es un directorio: {resolved}")

    known_files = ["index.faiss", "chunks.jsonl", "manifest.json"]
    existing = [name for name in known_files if (resolved / name).exists()]
    if existing and not overwrite:
        raise IndexBuildError(
            "El índice ya contiene artefactos. Use --overwrite para regenerarlo deliberadamente."
        )

    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def build_faiss_index(
    chunk_files: Sequence[Path],
    output_dir: Path,
    *,
    model_name: str = DEFAULT_EMBEDDING_MODEL,
    batch_size: int = 32,
    overwrite: bool = False,
    local_files_only: bool = False,
    provider: EmbeddingProvider | None = None,
    store: type[FaissVectorStore] = FaissVectorStore,
) -> IndexManifest:
    if not chunk_files:
        raise IndexBuildError("Debe proporcionar al menos un archivo JSONL de chunks.")

    build_started = time.perf_counter()
    started_tracing_here = not tracemalloc.is_tracing()
    if started_tracing_here:
        tracemalloc.start()

    chunks: list[LegalChunk] = []
    resolved_sources: list[str] = []
    source_hashes: list[str] = []
    try:
        for source in chunk_files:
            resolved = source.expanduser().resolve()
            chunks.extend(load_chunks_jsonl(resolved))
            resolved_sources.append(str(resolved))
            source_hashes.append(_sha256_file(resolved))

        _validate_unique_chunk_ids(chunks)
        destination = _safe_output_directory(output_dir, overwrite=overwrite)

        embedder = provider or SentenceTransformerEmbedder(
            model_name=model_name,
            batch_size=batch_size,
            device="cpu",
            local_files_only=local_files_only,
        )
        texts = [render_embedding_text(chunk) for chunk in chunks]
        max_embedding_text_chars = max(len(text) for text in texts)

        try:
            vectors = normalize_rows(embedder.encode(texts))
        except EmbeddingError as exc:
            raise IndexBuildError(str(exc)) from exc

        if vectors.shape[0] != len(chunks):
            raise IndexBuildError(
                "La cantidad de embeddings no coincide con la cantidad de chunks."
            )

        # El staging debe vivir en el mismo volumen que el destino.
        # os.replace() es atómico dentro del mismo filesystem, pero Windows
        # devuelve WinError 17 si Temp está en C: y el repositorio en D:.
        with tempfile.TemporaryDirectory(
            prefix=".tributarius-index-",
            dir=destination,
        ) as temp_name:
            temp_dir = Path(temp_name)
            temp_index = temp_dir / "index.faiss"
            temp_chunks = temp_dir / "chunks.jsonl"

            try:
                store.write(vectors, temp_index)
            except (FaissStoreError, OSError) as exc:
                raise IndexBuildError("No fue posible construir el índice FAISS.") from exc

            _write_chunks(chunks, temp_chunks)
            _, peak_memory = tracemalloc.get_traced_memory()
            elapsed = time.perf_counter() - build_started

            combined_source_hash = hashlib.sha256(
                "\n".join(source_hashes).encode("utf-8")
            ).hexdigest()
            manifest = IndexManifest(
                created_at_utc=datetime.now(UTC),
                model_name=embedder.model_name,
                vector_dimension=int(vectors.shape[1]),
                chunk_count=len(chunks),
                source_chunk_files=resolved_sources,
                index_sha256=_sha256_file(temp_index),
                chunks_sha256=_sha256_file(temp_chunks),
                source_chunks_sha256=combined_source_hash,
                index_bytes=temp_index.stat().st_size,
                chunks_bytes=temp_chunks.stat().st_size,
                build_seconds=elapsed,
                python_peak_memory_bytes=peak_memory,
                max_embedding_text_chars=max_embedding_text_chars,
            )
            temp_manifest = temp_dir / "manifest.json"
            temp_manifest.write_text(
                manifest.model_dump_json(indent=2),
                encoding="utf-8",
            )

            for filename in ("index.faiss", "chunks.jsonl", "manifest.json"):
                os.replace(temp_dir / filename, destination / filename)

        logger.info(
            "Índice vectorial construido: chunks=%s dimensión=%s output=%s",
            manifest.chunk_count,
            manifest.vector_dimension,
            destination,
        )
        return manifest
    finally:
        if started_tracing_here and tracemalloc.is_tracing():
            tracemalloc.stop()
