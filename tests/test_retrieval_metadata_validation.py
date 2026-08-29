from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.chunks import ChunkMetadata, LegalChunkType, LegalHierarchy
from app.domain.documents import SourceType


def _base() -> dict[str, object]:
    return {
        "document_id": "cff",
        "source_type": SourceType.NORMATIVA,
        "source_filename": "cff.md",
        "chunk_index": 0,
        "chunk_type": LegalChunkType.ARTICLE,
        "hierarchy": LegalHierarchy(),
        "source_sha256": "a" * 64,
    }


def test_retrieval_index_requires_parent_chunk_id() -> None:
    with pytest.raises(ValidationError):
        ChunkMetadata(
            **_base(),
            retrieval_subchunk_index=0,
            retrieval_subchunk_count=1,
        )


def test_retrieval_index_must_be_less_than_count() -> None:
    with pytest.raises(ValidationError):
        ChunkMetadata(
            **_base(),
            parent_chunk_id="parent-chunk-0001",
            retrieval_subchunk_index=1,
            retrieval_subchunk_count=1,
        )
