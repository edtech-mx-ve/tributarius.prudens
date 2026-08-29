from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from typing import Protocol

from app.domain.chunks import LegalChunk
from rag.indexing.builder import render_embedding_text

_PARAGRAPH_RE = re.compile(r"\n\s*\n+")
_SENTENCE_RE = re.compile(r"(?<=[.!?;:])\s+(?=[A-ZÁÉÍÓÚÑ0-9(])")


class RetrievalSubchunkError(RuntimeError):
    """Error controlado al construir subchunks de recuperación."""


class TokenCounter(Protocol):
    @property
    def max_seq_length(self) -> int: ...

    def count_tokens(self, text: str) -> int: ...


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _retrieval_chunk_id(parent_chunk_id: str, index: int, text: str) -> str:
    payload = f"{parent_chunk_id}|{index}|{_sha256_text(text)}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
    return f"r19f-{digest}"


def _preview_chunk(parent: LegalChunk, text: str) -> LegalChunk:
    metadata = parent.metadata.model_copy(
        update={
            "parent_chunk_id": parent.chunk_id,
            "retrieval_subchunk_index": 0,
            "retrieval_subchunk_count": 1,
            "retrieval_strategy": "semantic_legal_v1",
            "retrieval_text_sha256": _sha256_text(text),
        }
    )
    return LegalChunk(
        chunk_id="r19f-preview",
        text=text,
        metadata=metadata,
    )


def _fits(
    parent: LegalChunk,
    text: str,
    token_counter: TokenCounter,
    max_seq_length: int,
) -> bool:
    rendered = render_embedding_text(_preview_chunk(parent, text))
    return token_counter.count_tokens(rendered) <= max_seq_length


def _split_long_words(
    parent: LegalChunk,
    text: str,
    token_counter: TokenCounter,
    max_seq_length: int,
    *,
    overlap_words: int,
) -> list[str]:
    words = text.split()
    if not words:
        return []
    parts: list[str] = []
    start = 0

    while start < len(words):
        low = start + 1
        high = len(words)
        best: int | None = None
        while low <= high:
            middle = (low + high) // 2
            candidate = " ".join(words[start:middle])
            if _fits(parent, candidate, token_counter, max_seq_length):
                best = middle
                low = middle + 1
            else:
                high = middle - 1

        if best is None:
            raise RetrievalSubchunkError(
                f"El contexto del chunk {parent.chunk_id} no deja espacio "
                "para un solo token de contenido."
            )

        part = " ".join(words[start:best]).strip()
        if part:
            parts.append(part)

        if best >= len(words):
            break
        width = best - start
        effective_overlap = min(overlap_words, max(0, width - 1))
        start = best - effective_overlap

    return parts


def _atomic_segments(
    parent: LegalChunk,
    token_counter: TokenCounter,
    max_seq_length: int,
    *,
    overlap_words: int,
) -> list[str]:
    paragraphs = [
        item.strip()
        for item in _PARAGRAPH_RE.split(parent.text)
        if item.strip()
    ]
    if not paragraphs:
        paragraphs = [parent.text.strip()]

    atoms: list[str] = []
    for paragraph in paragraphs:
        if _fits(parent, paragraph, token_counter, max_seq_length):
            atoms.append(paragraph)
            continue

        sentences = [
            item.strip()
            for item in _SENTENCE_RE.split(paragraph)
            if item.strip()
        ]
        if len(sentences) == 1:
            atoms.extend(
                _split_long_words(
                    parent,
                    paragraph,
                    token_counter,
                    max_seq_length,
                    overlap_words=overlap_words,
                )
            )
            continue

        for sentence in sentences:
            if _fits(parent, sentence, token_counter, max_seq_length):
                atoms.append(sentence)
            else:
                atoms.extend(
                    _split_long_words(
                        parent,
                        sentence,
                        token_counter,
                        max_seq_length,
                        overlap_words=overlap_words,
                    )
                )
    return atoms


def _pack_atoms(
    parent: LegalChunk,
    atoms: Sequence[str],
    token_counter: TokenCounter,
    max_seq_length: int,
) -> list[str]:
    packed: list[str] = []
    current = ""

    for atom in atoms:
        candidate = atom if not current else f"{current}\n\n{atom}"
        if _fits(parent, candidate, token_counter, max_seq_length):
            current = candidate
            continue

        if current:
            packed.append(current)
        current = atom

    if current:
        packed.append(current)

    return packed


def split_parent_chunk(
    parent: LegalChunk,
    token_counter: TokenCounter,
    *,
    overlap_words: int = 12,
) -> list[LegalChunk]:
    if overlap_words < 0 or overlap_words > 64:
        raise RetrievalSubchunkError("overlap_words debe estar entre 0 y 64.")

    max_seq_length = token_counter.max_seq_length
    if max_seq_length < 16:
        raise RetrievalSubchunkError("max_seq_length es demasiado pequeño.")

    if _fits(parent, parent.text, token_counter, max_seq_length):
        texts = [parent.text.strip()]
    else:
        atoms = _atomic_segments(
            parent,
            token_counter,
            max_seq_length,
            overlap_words=overlap_words,
        )
        texts = _pack_atoms(parent, atoms, token_counter, max_seq_length)

    if not texts:
        raise RetrievalSubchunkError(
            f"No fue posible producir subchunks para {parent.chunk_id}."
        )

    total = len(texts)
    chunks: list[LegalChunk] = []
    for index, text in enumerate(texts):
        metadata = parent.metadata.model_copy(
            update={
                "parent_chunk_id": parent.chunk_id,
                "retrieval_subchunk_index": index,
                "retrieval_subchunk_count": total,
                "retrieval_strategy": "semantic_legal_v1",
                "retrieval_text_sha256": _sha256_text(text),
            }
        )
        chunk = LegalChunk(
            chunk_id=_retrieval_chunk_id(parent.chunk_id, index, text),
            text=text,
            metadata=metadata,
        )
        rendered_tokens = token_counter.count_tokens(render_embedding_text(chunk))
        if rendered_tokens > max_seq_length:
            raise RetrievalSubchunkError(
                f"Subchunk {chunk.chunk_id} excede el límite: "
                f"{rendered_tokens}>{max_seq_length}."
            )
        chunks.append(chunk)

    return chunks


def build_retrieval_subchunks(
    parents: Sequence[LegalChunk],
    token_counter: TokenCounter,
    *,
    overlap_words: int = 12,
) -> list[LegalChunk]:
    if not parents:
        raise RetrievalSubchunkError("Se requiere al menos un chunk canónico.")

    retrieval_chunks: list[LegalChunk] = []
    seen_ids: set[str] = set()
    for parent in parents:
        for chunk in split_parent_chunk(
            parent,
            token_counter,
            overlap_words=overlap_words,
        ):
            if chunk.chunk_id in seen_ids:
                raise RetrievalSubchunkError(
                    f"chunk_id de recuperación duplicado: {chunk.chunk_id}"
                )
            seen_ids.add(chunk.chunk_id)
            retrieval_chunks.append(chunk)

    return retrieval_chunks
