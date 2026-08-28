import hashlib
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from app.domain.chunks import ChunkMetadata, LegalChunk, LegalChunkType, LegalHierarchy
from app.domain.documents import SourceType
from rag.indexing.models import IndexManifest
from rag.retrieval.filters import RetrievalFilters
from rag.retrieval.retriever import FaissRetriever, RetrievalError


class FakeEmbedder:
    model_name = "fake/test-model"

    def encode(self, texts: list[str]) -> np.ndarray:
        assert len(texts) == 1
        return np.asarray([[1.0, 0.0]], dtype=np.float32)


class FakeStore:
    @staticmethod
    def read(path: Path) -> SimpleNamespace:
        assert path.name == "index.faiss"
        return SimpleNamespace(ntotal=3, d=2)

    @staticmethod
    def search(
        index: object, query_vector: object, *, top_k: int
    ) -> tuple[np.ndarray, np.ndarray]:
        scores = np.asarray([0.95, 0.80, 0.70], dtype=np.float32)[:top_k]
        positions = np.asarray([0, 1, 2], dtype=np.int64)[:top_k]
        return scores, positions


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def chunk(index: int, source_type: SourceType, year: int | None) -> LegalChunk:
    return LegalChunk(
        chunk_id=f"chunk-{index:04d}",
        text=f"Texto jurídico {index}",
        metadata=ChunkMetadata(
            document_id=f"doc-{index}",
            source_type=source_type,
            source_filename=f"doc-{index}.pdf",
            chunk_index=index,
            chunk_type=LegalChunkType.ARTICLE,
            legal_identifier=str(index + 1),
            page_start=1,
            page_end=1,
            hierarchy=LegalHierarchy(article=str(index + 1)),
            source_sha256="a" * 64,
            fiscal_year=year,
        ),
    )


def make_index_dir(tmp_path: Path) -> Path:
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    chunks = [
        chunk(0, SourceType.NORMATIVA, 2026),
        chunk(1, SourceType.JURISPRUDENCIA, None),
        chunk(2, SourceType.NORMATIVA, 2025),
    ]
    chunks_path = index_dir / "chunks.jsonl"
    chunks_path.write_text(
        "\n".join(item.model_dump_json() for item in chunks) + "\n",
        encoding="utf-8",
    )
    index_path = index_dir / "index.faiss"
    index_path.write_bytes(b"fake-index")
    manifest = IndexManifest(
        created_at_utc="2026-08-27T00:00:00Z",
        model_name="fake/test-model",
        vector_dimension=2,
        chunk_count=3,
        source_chunk_files=["test.jsonl"],
        index_sha256=sha(index_path),
        chunks_sha256=sha(chunks_path),
    )
    (index_dir / "manifest.json").write_text(
        manifest.model_dump_json(indent=2), encoding="utf-8"
    )
    return index_dir


def test_retriever_returns_ranked_hits(tmp_path: Path) -> None:
    retriever = FaissRetriever(
        make_index_dir(tmp_path),
        FakeEmbedder(),
        store=FakeStore,  # type: ignore[arg-type]
    )

    result = retriever.search("obligaciones fiscales", top_k=2)

    assert [hit.chunk_id for hit in result.hits] == ["chunk-0000", "chunk-0001"]
    assert result.returned_count == 2


def test_retriever_filters_normativa_by_year(tmp_path: Path) -> None:
    retriever = FaissRetriever(
        make_index_dir(tmp_path),
        FakeEmbedder(),
        store=FakeStore,  # type: ignore[arg-type]
    )
    filters = RetrievalFilters(
        source_types={SourceType.NORMATIVA},
        fiscal_year=2026,
    )

    result = retriever.search("ISR", top_k=5, filters=filters)

    assert [hit.chunk_id for hit in result.hits] == ["chunk-0000"]
    assert result.candidate_count == 1


def test_retriever_rejects_model_mismatch(tmp_path: Path) -> None:
    embedder = FakeEmbedder()
    embedder.model_name = "other/model"  # type: ignore[misc]

    with pytest.raises(RetrievalError, match="modelo"):
        FaissRetriever(
            make_index_dir(tmp_path),
            embedder,
            store=FakeStore,  # type: ignore[arg-type]
        )


def test_retriever_rejects_empty_query(tmp_path: Path) -> None:
    retriever = FaissRetriever(
        make_index_dir(tmp_path),
        FakeEmbedder(),
        store=FakeStore,  # type: ignore[arg-type]
    )

    with pytest.raises(RetrievalError, match="vacía"):
        retriever.search("   ")
