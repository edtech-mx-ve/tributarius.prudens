from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from pathlib import Path

from pydantic import ValidationError

from app.domain.chunks import LegalChunk
from rag.indexing.models import IndexManifest
from rag.retrieval.filters import RetrievalFilters
from rag.retrieval.models import RetrievalHit, RetrievalResult
from rag.retrieval.retriever import RetrievalError

_WORD_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_STOPWORDS = frozenset(
    {
        "a", "al", "de", "del", "el", "en", "la", "las", "los", "para",
        "por", "que", "se", "su", "sus", "un", "una", "y",
    }
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _tokens(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    without_marks = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return {
        token
        for token in _WORD_RE.findall(without_marks)
        if len(token) > 1 and token not in _STOPWORDS
    }


def _metadata_text(chunk: LegalChunk) -> str:
    metadata = chunk.metadata
    values: list[str] = [
        metadata.document_id,
        metadata.legal_identifier or "",
    ]
    for name in ("title", "source_unit_label", "source_role"):
        value = getattr(metadata, name, None)
        if isinstance(value, str):
            values.append(value)
    matter = getattr(metadata, "matter", None)
    if isinstance(matter, (list, tuple, set)):
        values.extend(str(item) for item in matter)
    return " ".join(values)


def _lexical_score(query_tokens: set[str], chunk: LegalChunk) -> float:
    if not query_tokens:
        return 0.0
    text_tokens = _tokens(f"{chunk.text} {_metadata_text(chunk)}")
    if not text_tokens:
        return 0.0
    matched = len(query_tokens & text_tokens)
    if matched == 0:
        return 0.0
    coverage = matched / len(query_tokens)
    density = matched / math.sqrt(len(query_tokens) * len(text_tokens))
    return min(1.0, 0.9 * coverage + 0.1 * density)


class CpuLexicalRetriever:
    """Retriever CPU de contingencia sin Torch/FAISS en memoria.

    Conserva el contrato ``search`` usado por ``LegalHybridRetriever`` y valida
    el mismo bundle publicado antes de aceptar consultas. Está diseñado para el
    perfil ``stateless_free`` de 512 MB, donde materializar SentenceTransformer
    + Torch puede exceder el presupuesto de memoria.

    Este backend no se presenta como recuperación semántica: su ``score`` es
    lexical determinista. El reranking jurídico existente sigue operando encima.
    """

    def __init__(self, index_dir: Path, *, verify_integrity: bool = True) -> None:
        self._index_dir = index_dir.expanduser().resolve()
        self._manifest = self._load_manifest()
        self._chunks = self._load_chunks()

        index_path = self._index_dir / self._manifest.index_filename
        chunks_path = self._index_dir / self._manifest.chunks_filename
        if verify_integrity:
            self._verify_hash(index_path, self._manifest.index_sha256, "índice")
            self._verify_hash(chunks_path, self._manifest.chunks_sha256, "chunks")

        if self._manifest.chunk_count != len(self._chunks):
            raise RetrievalError(
                "El número de chunks no coincide con manifest.json."
            )

    def _load_manifest(self) -> IndexManifest:
        path = self._index_dir / "manifest.json"
        try:
            return IndexManifest.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValidationError) as exc:
            raise RetrievalError("manifest.json no existe o es inválido.") from exc

    def _load_chunks(self) -> list[LegalChunk]:
        path = self._index_dir / self._manifest.chunks_filename
        chunks: list[LegalChunk] = []
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line_number, raw in enumerate(handle, start=1):
                    if not raw.strip():
                        continue
                    try:
                        chunks.append(LegalChunk.model_validate_json(raw))
                    except ValidationError as exc:
                        raise RetrievalError(
                            f"Chunk inválido en línea {line_number}."
                        ) from exc
        except (OSError, UnicodeError) as exc:
            raise RetrievalError("No fue posible leer chunks.jsonl.") from exc
        if not chunks:
            raise RetrievalError("chunks.jsonl está vacío.")
        return chunks

    @staticmethod
    def _verify_hash(path: Path, expected: str, label: str) -> None:
        if not path.is_file() or _sha256_file(path) != expected:
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

        query_tokens = _tokens(clean_query)
        active_filters = filters or RetrievalFilters()
        scored: list[tuple[float, str, LegalChunk]] = []
        candidate_count = 0

        for chunk in self._chunks:
            metadata = chunk.metadata
            if not active_filters.matches(
                source_type=metadata.source_type,
                chunk_type=metadata.chunk_type,
                fiscal_year=metadata.fiscal_year,
                version_label=metadata.version_label,
                document_id=metadata.document_id,
            ):
                continue
            candidate_count += 1
            score = _lexical_score(query_tokens, chunk)
            if score > 0.0:
                scored.append((score, chunk.chunk_id, chunk))

        scored.sort(key=lambda row: (-row[0], row[1]))
        selected = scored[:top_k]
        hits = [
            RetrievalHit(
                rank=rank,
                score=float(score),
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                metadata=chunk.metadata,
            )
            for rank, (score, _chunk_id, chunk) in enumerate(selected, start=1)
        ]
        return RetrievalResult(
            query=clean_query,
            requested_top_k=top_k,
            candidate_count=candidate_count,
            returned_count=len(hits),
            hits=hits,
        )
