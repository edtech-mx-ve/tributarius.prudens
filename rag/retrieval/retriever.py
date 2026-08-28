from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
from pydantic import ValidationError

from app.domain.chunks import LegalChunk
from rag.embeddings.provider import EmbeddingError, EmbeddingProvider
from rag.indexing.faiss_store import FaissStoreError, FaissVectorStore
from rag.indexing.models import IndexManifest
from rag.retrieval.filters import RetrievalFilters
from rag.retrieval.models import RetrievalHit, RetrievalResult


class RetrievalError(RuntimeError):
    """Error controlado del retriever."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class FaissRetriever:
    def __init__(
        self,
        index_dir: Path,
        embedder: EmbeddingProvider,
        *,
        verify_integrity: bool = True,
        store: type[FaissVectorStore] = FaissVectorStore,
    ) -> None:
        self._index_dir = index_dir.expanduser().resolve()
        self._embedder = embedder
        self._store = store
        self._manifest = self._load_manifest()
        self._chunks = self._load_chunks()

        index_path = self._index_dir / self._manifest.index_filename
        chunks_path = self._index_dir / self._manifest.chunks_filename
        if verify_integrity:
            self._verify_hash(index_path, self._manifest.index_sha256, "índice")
            self._verify_hash(chunks_path, self._manifest.chunks_sha256, "chunks")

        try:
            self._index = self._store.read(index_path)
        except FaissStoreError as exc:
            raise RetrievalError(str(exc)) from exc

        if int(self._index.ntotal) != len(self._chunks):
            raise RetrievalError(
                "El número de vectores FAISS no coincide con chunks.jsonl."
            )
        if int(self._index.d) != self._manifest.vector_dimension:
            raise RetrievalError(
                "La dimensión del índice no coincide con manifest.json."
            )
        if self._embedder.model_name != self._manifest.model_name:
            raise RetrievalError(
                "El modelo de consulta no coincide con el usado para construir el índice."
            )

    def _load_manifest(self) -> IndexManifest:
        path = self._index_dir / "manifest.json"
        try:
            return IndexManifest.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError) as exc:
            raise RetrievalError("manifest.json no existe o es inválido.") from exc

    def _load_chunks(self) -> list[LegalChunk]:
        path = self._index_dir / self._manifest.chunks_filename
        chunks: list[LegalChunk] = []
        try:
            for line_number, raw in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if not raw.strip():
                    continue
                try:
                    chunks.append(LegalChunk.model_validate_json(raw))
                except ValidationError as exc:
                    raise RetrievalError(
                        f"Chunk inválido en línea {line_number}."
                    ) from exc
        except OSError as exc:
            raise RetrievalError("No fue posible leer chunks.jsonl.") from exc

        if not chunks:
            raise RetrievalError("chunks.jsonl está vacío.")
        return chunks

    @staticmethod
    def _verify_hash(path: Path, expected: str, label: str) -> None:
        if not path.exists() or _sha256_file(path) != expected:
            raise RetrievalError(f"Falló la verificación SHA-256 de {label}.")

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> RetrievalResult:
        clean_query = query.strip()
        if not clean_query:
            raise RetrievalError("La consulta no puede estar vacía.")
        if top_k < 1 or top_k > 100:
            raise RetrievalError("top_k debe estar entre 1 y 100.")

        active_filters = filters or RetrievalFilters()
        candidate_positions = [
            index
            for index, chunk in enumerate(self._chunks)
            if active_filters.matches(
                source_type=chunk.metadata.source_type,
                chunk_type=chunk.metadata.chunk_type,
                fiscal_year=chunk.metadata.fiscal_year,
                version_label=chunk.metadata.version_label,
                document_id=chunk.metadata.document_id,
            )
        ]
        if not candidate_positions:
            return RetrievalResult(
                query=clean_query,
                requested_top_k=top_k,
                candidate_count=0,
                returned_count=0,
                hits=[],
            )

        try:
            vector = self._embedder.encode([clean_query])
        except EmbeddingError as exc:
            raise RetrievalError(str(exc)) from exc

        # FAISS searches a wider pool, then deterministic metadata filtering is applied.
        # If filters are selective, querying all rows guarantees enough eligible hits.
        search_k = len(self._chunks) if active_filters != RetrievalFilters() else min(
            len(self._chunks), top_k
        )
        try:
            scores, positions = self._store.search(
                self._index, np.asarray(vector, dtype=np.float32), top_k=search_k
            )
        except FaissStoreError as exc:
            raise RetrievalError(str(exc)) from exc

        eligible = set(candidate_positions)
        hits: list[RetrievalHit] = []
        for score, position in zip(scores.tolist(), positions.tolist(), strict=True):
            if position < 0 or position not in eligible:
                continue
            chunk = self._chunks[position]
            hits.append(
                RetrievalHit(
                    rank=len(hits) + 1,
                    score=float(score),
                    chunk_id=chunk.chunk_id,
                    text=chunk.text,
                    metadata=chunk.metadata,
                )
            )
            if len(hits) >= top_k:
                break

        return RetrievalResult(
            query=clean_query,
            requested_top_k=top_k,
            candidate_count=len(candidate_positions),
            returned_count=len(hits),
            hits=hits,
        )
