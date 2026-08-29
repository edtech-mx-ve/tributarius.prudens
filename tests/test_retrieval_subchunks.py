from __future__ import annotations

from app.domain.chunks import (
    ChunkMetadata,
    LegalChunk,
    LegalChunkType,
    LegalHierarchy,
)
from app.domain.documents import SourceType
from rag.chunking.retrieval_subchunks import (
    build_retrieval_subchunks,
    split_parent_chunk,
)
from rag.indexing.builder import render_embedding_text


class WhitespaceTokenCounter:
    max_seq_length = 48

    def count_tokens(self, text: str) -> int:
        return len(text.split())


def _parent(text: str, *, chunk_id: str = "parent-chunk-0001") -> LegalChunk:
    return LegalChunk(
        chunk_id=chunk_id,
        text=text,
        metadata=ChunkMetadata(
            document_id="cff",
            source_type=SourceType.NORMATIVA,
            source_filename="cff.md",
            chunk_index=0,
            chunk_type=LegalChunkType.ARTICLE,
            legal_identifier="Artículo 1",
            hierarchy=LegalHierarchy(article="Artículo 1"),
            source_sha256="a" * 64,
            title="Código Fiscal de la Federación",
            source_unit_label="Artículo 1",
        ),
    )


def test_short_parent_still_gets_retrieval_trace() -> None:
    parent = _parent("Texto tributario breve con obligación fiscal aplicable.")

    chunks = split_parent_chunk(parent, WhitespaceTokenCounter())

    assert len(chunks) == 1
    assert chunks[0].metadata.parent_chunk_id == parent.chunk_id
    assert chunks[0].metadata.retrieval_subchunk_index == 0
    assert chunks[0].metadata.retrieval_subchunk_count == 1
    assert chunks[0].metadata.retrieval_text_sha256 is not None


def test_long_parent_is_split_without_exceeding_model_limit() -> None:
    text = " ".join(
        f"obligación{i} fiscal contribuyente."
        for i in range(120)
    )
    parent = _parent(text)

    chunks = split_parent_chunk(
        parent,
        WhitespaceTokenCounter(),
        overlap_words=4,
    )

    assert len(chunks) > 1
    assert all(chunk.metadata.parent_chunk_id == parent.chunk_id for chunk in chunks)
    assert all(
        WhitespaceTokenCounter().count_tokens(render_embedding_text(chunk))
        <= WhitespaceTokenCounter.max_seq_length
        for chunk in chunks
    )
    assert [chunk.metadata.retrieval_subchunk_index for chunk in chunks] == list(
        range(len(chunks))
    )
    assert all(
        chunk.metadata.retrieval_subchunk_count == len(chunks)
        for chunk in chunks
    )


def test_build_preserves_all_parent_chunks_and_unique_ids() -> None:
    parents = [
        _parent(" ".join(["derecho fiscal."] * 100), chunk_id="parent-chunk-0001"),
        _parent(" ".join(["impuesto federal."] * 100), chunk_id="parent-chunk-0002"),
    ]

    chunks = build_retrieval_subchunks(
        parents,
        WhitespaceTokenCounter(),
        overlap_words=2,
    )

    parent_ids = {chunk.metadata.parent_chunk_id for chunk in chunks}
    chunk_ids = [chunk.chunk_id for chunk in chunks]
    assert parent_ids == {"parent-chunk-0001", "parent-chunk-0002"}
    assert len(chunk_ids) == len(set(chunk_ids))


def test_compact_embedding_context_is_used_for_retrieval_chunk() -> None:
    parent = _parent("Derechos del contribuyente y obligaciones tributarias.")

    chunk = split_parent_chunk(parent, WhitespaceTokenCounter())[0]
    rendered = render_embedding_text(chunk)

    assert "Fuente: normativa" in rendered
    assert "Unidad: Artículo 1" in rendered
    assert "Texto:" in rendered
    assert "Tipo documental:" not in rendered
