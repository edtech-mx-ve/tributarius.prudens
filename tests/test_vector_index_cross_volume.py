from __future__ import annotations

import tempfile
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

from app.domain.chunks import (
    ChunkMetadata,
    LegalChunk,
    LegalChunkType,
    LegalHierarchy,
)
from app.domain.documents import SourceType
from rag.indexing.builder import build_faiss_index


class FakeEmbedder:
    model_name = "fake/test-model"

    def encode(self, texts: Sequence[str]) -> NDArray[np.float32]:
        return np.ones((len(texts), 3), dtype=np.float32)


class FakeStore:
    @staticmethod
    def write(vectors: object, path: Path) -> Path:
        path.write_bytes(np.asarray(vectors, dtype=np.float32).tobytes())
        return path


def test_staging_directory_is_created_inside_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.jsonl"
    chunk = LegalChunk(
        chunk_id="test-chunk",
        text="Texto fiscal.",
        metadata=ChunkMetadata(
            document_id="doc",
            source_type=SourceType.NORMATIVA,
            source_filename="doc.md",
            chunk_index=0,
            chunk_type=LegalChunkType.ARTICLE,
            hierarchy=LegalHierarchy(),
            source_sha256="a" * 64,
        ),
    )
    source.write_text(chunk.model_dump_json() + "\n", encoding="utf-8")
    output = tmp_path / "runtime"

    real_temp = tempfile.TemporaryDirectory
    captured_dirs: list[Path | str | None] = []

    def recording_tempdir(
        suffix: str | None = None,
        prefix: str | None = None,
        dir: str | Path | None = None,
        ignore_cleanup_errors: bool = False,
        *,
        delete: bool = True,
    ) -> tempfile.TemporaryDirectory[str]:
        captured_dirs.append(dir)
        return real_temp(
            suffix=suffix,
            prefix=prefix,
            dir=dir,
            ignore_cleanup_errors=ignore_cleanup_errors,
            delete=delete,
        )

    monkeypatch.setattr(
        "rag.indexing.builder.tempfile.TemporaryDirectory",
        recording_tempdir,
    )

    manifest = build_faiss_index(
        [source],
        output,
        provider=FakeEmbedder(),
        store=FakeStore,  # type: ignore[arg-type]
    )

    assert manifest.chunk_count == 1
    assert len(captured_dirs) == 1
    assert captured_dirs[0] is not None
    assert Path(captured_dirs[0]).resolve() == output.resolve()
    assert (output / "index.faiss").is_file()
