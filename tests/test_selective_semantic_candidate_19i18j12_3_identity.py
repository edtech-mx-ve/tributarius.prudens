from __future__ import annotations

import pytest

from app.services.selective_semantic_candidate import (
    SelectiveSemanticCandidateError,
    _chunk_document_id,
)


def test_document_id_from_top_level_canonical_chunk() -> None:
    assert _chunk_document_id({"document_id": "cff"}) == "cff"


def test_canonical_id_from_top_level_is_supported() -> None:
    assert _chunk_document_id({"canonical_id": "lfdc"}) == "lfdc"


def test_document_id_from_nested_metadata_is_supported() -> None:
    assert (
        _chunk_document_id({"metadata": {"document_id": "reg_liva_250914"}})
        == "reg_liva_250914"
    )


def test_missing_document_identity_fails_closed() -> None:
    with pytest.raises(SelectiveSemanticCandidateError):
        _chunk_document_id({"chunk_id": "x", "text": "sin identidad"})
