from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

from app.domain.chunks import ChunkMetadata, LegalChunk, LegalChunkType, LegalHierarchy
from app.domain.documents import SourceType
from rag.indexing.builder import (
    IndexBuildError,
    build_faiss_index,
    load_chunks_jsonl,
    render_embedding_text,
)


class FakeEmbedder:
    model_name = "fake/test-model"

    def encode(self, texts: Sequence[str]) -> NDArray[np.float32]:
        vectors = []
        for index, text in enumerate(texts, start=1):
            vectors.append([float(index), float(len(text) % 11 + 1), 1.0])
        return np.asarray(vectors, dtype=np.float32)


class FakeStore:
    @staticmethod
    def write(vectors: object, path: Path) -> Path:
        array = np.asarray(vectors, dtype=np.float32)
        path.write_bytes(array.tobytes())
        return path


def make_chunk(index: int, text: str) -> LegalChunk:
    return LegalChunk(
        chunk_id=f"doc-1-chunk-{index:05d}-abcdef123456",
        text=text,
        metadata=ChunkMetadata(
            document_id="doc-1",
            source_type=SourceType.NORMATIVA,
            source_filename="ley.pdf",
            chunk_index=index,
            chunk_type=LegalChunkType.ARTICLE,
            legal_identifier=str(index + 1),
            page_start=index + 1,
            page_end=index + 1,
            hierarchy=LegalHierarchy(
                title="TÍTULO PRIMERO",
                chapter="CAPÍTULO I",
                article=str(index + 1),
            ),
            source_sha256="a" * 64,
        ),
    )


def write_jsonl(path: Path, chunks: list[LegalChunk]) -> None:
    path.write_text(
        "\n".join(chunk.model_dump_json() for chunk in chunks) + "\n",
        encoding="utf-8",
    )


def test_load_chunks_jsonl_round_trip(tmp_path: Path) -> None:
    source = tmp_path / "chunks.jsonl"
    chunks = [make_chunk(0, "Contenido uno."), make_chunk(1, "Contenido dos.")]
    write_jsonl(source, chunks)

    loaded = load_chunks_jsonl(source)

    assert [chunk.chunk_id for chunk in loaded] == [chunk.chunk_id for chunk in chunks]


def test_render_embedding_text_includes_legal_context() -> None:
    text = render_embedding_text(make_chunk(0, "Obligación tributaria."))

    assert "Fuente: normativa" in text
    assert "Título: TÍTULO PRIMERO" in text
    assert "Capítulo: CAPÍTULO I" in text
    assert "Artículo: 1" in text
    assert "Texto: Obligación tributaria." in text


def test_build_index_persists_manifest_and_chunks(tmp_path: Path) -> None:
    source = tmp_path / "input.jsonl"
    output = tmp_path / "index"
    write_jsonl(source, [make_chunk(0, "Uno"), make_chunk(1, "Dos")])

    manifest = build_faiss_index(
        [source],
        output,
        provider=FakeEmbedder(),
        store=FakeStore,  # type: ignore[arg-type]
    )

    assert manifest.chunk_count == 2
    assert manifest.vector_dimension == 3
    assert manifest.normalized is True
    assert (output / "index.faiss").is_file()
    assert (output / "chunks.jsonl").is_file()
    assert (output / "manifest.json").is_file()


def test_build_index_rejects_duplicate_chunk_ids(tmp_path: Path) -> None:
    source = tmp_path / "input.jsonl"
    chunk = make_chunk(0, "Uno")
    write_jsonl(source, [chunk, chunk])

    with pytest.raises(IndexBuildError, match="duplicados"):
        build_faiss_index(
            [source],
            tmp_path / "index",
            provider=FakeEmbedder(),
            store=FakeStore,  # type: ignore[arg-type]
        )


def test_build_index_refuses_silent_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "input.jsonl"
    output = tmp_path / "index"
    write_jsonl(source, [make_chunk(0, "Uno")])

    build_faiss_index(
        [source],
        output,
        provider=FakeEmbedder(),
        store=FakeStore,  # type: ignore[arg-type]
    )

    with pytest.raises(IndexBuildError, match="--overwrite"):
        build_faiss_index(
            [source],
            output,
            provider=FakeEmbedder(),
            store=FakeStore,  # type: ignore[arg-type]
        )


def test_build_index_explicit_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "input.jsonl"
    output = tmp_path / "index"
    write_jsonl(source, [make_chunk(0, "Uno")])

    first = build_faiss_index(
        [source],
        output,
        provider=FakeEmbedder(),
        store=FakeStore,  # type: ignore[arg-type]
    )
    second = build_faiss_index(
        [source],
        output,
        provider=FakeEmbedder(),
        store=FakeStore,  # type: ignore[arg-type]
        overwrite=True,
    )

    assert first.chunk_count == second.chunk_count == 1
