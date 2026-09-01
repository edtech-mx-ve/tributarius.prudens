from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from app.domain.chunks import LegalChunkType
from app.domain.documents import SourceType
from app.domain.legal_chunks import LegalChunk as CorpusLegalChunk
from app.domain.legal_chunks import LegalUnitType
from rag.indexing.builder import build_faiss_index, load_chunks_jsonl
from rag.indexing.runtime_adapter import adapt_corpus_chunk


class FakeEmbedder:
    model_name = "fake/test-model"

    def encode(self, texts: Sequence[str]) -> NDArray[np.float32]:
        return np.asarray(
            [[float(index + 1), 1.0, 2.0] for index, _ in enumerate(texts)],
            dtype=np.float32,
        )


class FakeStore:
    @staticmethod
    def write(vectors: object, path: Path) -> Path:
        path.write_bytes(np.asarray(vectors, dtype=np.float32).tobytes())
        return path


def corpus_chunk(
    *,
    canonical_id: str = "lisr",
    unit_type: LegalUnitType = LegalUnitType.ARTICLE,
    unit_label: str = "Artículo 1",
) -> CorpusLegalChunk:
    return CorpusLegalChunk(
        chunk_id=f"{canonical_id}:{unit_type.value}:articulo-1:00001:abcdef1234567890",
        canonical_id=canonical_id,
        source_role="ley",
        document_type="ley",
        title="Documento fiscal",
        unit_type=unit_type,
        unit_label=unit_label,
        hierarchy=["TÍTULO I", "CAPÍTULO I"],
        page_start=1,
        page_end=2,
        fiscal_year=2026,
        source_sha256="a" * 64,
        text_sha256="b" * 64,
        text="Texto jurídico recuperable.",
        matter=["isr"],
        jurisdiction="México",
        effective_from="2026-01-01",
    )


def test_adapter_preserves_traceability_metadata() -> None:
    runtime = adapt_corpus_chunk(corpus_chunk(), chunk_index=7)

    assert runtime.metadata.document_id == "lisr"
    assert runtime.metadata.source_type is SourceType.NORMATIVA
    assert runtime.metadata.chunk_type is LegalChunkType.ARTICLE
    assert runtime.metadata.chunk_index == 7
    assert runtime.metadata.canonical_id == "lisr"
    assert runtime.metadata.source_role == "ley"
    assert runtime.metadata.matter == ["isr"]
    assert runtime.metadata.text_sha256 == "b" * 64


def test_adapter_maps_unam_and_prodecon_sources() -> None:
    unam = adapt_corpus_chunk(
        corpus_chunk(
            canonical_id="manual_derecho_fiscal_unam",
            unit_type=LegalUnitType.ACADEMIC_CHAPTER,
            unit_label="Capítulo I",
        ),
        chunk_index=0,
    )
    prodecon = adapt_corpus_chunk(
        corpus_chunk(
            canonical_id="prodecon_contribuyente",
            unit_type=LegalUnitType.PRODECON_SECTION,
            unit_label="PRODECON-01",
        ),
        chunk_index=1,
    )

    assert unam.metadata.source_type is SourceType.UNAM
    assert unam.metadata.chunk_type is LegalChunkType.CHAPTER
    assert prodecon.metadata.source_type is SourceType.PRODECON
    assert prodecon.metadata.chunk_type is LegalChunkType.SECTION


def test_loader_accepts_sprint19c_jsonl(tmp_path: Path) -> None:
    source = tmp_path / "chunks.jsonl"
    chunk = corpus_chunk()
    source.write_text(chunk.model_dump_json() + "\n", encoding="utf-8")

    loaded = load_chunks_jsonl(source)

    assert len(loaded) == 1
    assert loaded[0].metadata.canonical_id == "lisr"


def test_builder_persists_runtime_artifacts_from_sprint19c(tmp_path: Path) -> None:
    source = tmp_path / "chunks.jsonl"
    source.write_text(
        "\n".join(
            [
                corpus_chunk().model_dump_json(),
                corpus_chunk(
                    canonical_id="liva",
                    unit_label="Artículo 2",
                ).model_copy(
                    update={
                        "chunk_id": (
                            "liva:article:articulo-2:00002:1234567890abcdef"
                        )
                    }
                ).model_dump_json(),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "runtime"

    manifest = build_faiss_index(
        [source],
        output,
        provider=FakeEmbedder(),
        store=FakeStore,  # type: ignore[arg-type]
    )

    assert manifest.chunk_count == 2
    assert manifest.vector_dimension == 3
    assert manifest.index_bytes is not None
    assert manifest.chunks_bytes is not None
    assert manifest.build_seconds is not None
    assert manifest.max_embedding_text_chars is not None
    assert (output / "index.faiss").is_file()
    assert (output / "chunks.jsonl").is_file()
    assert (output / "manifest.json").is_file()
