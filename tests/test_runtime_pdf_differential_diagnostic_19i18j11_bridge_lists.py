from __future__ import annotations

from app.services.runtime_pdf_differential_diagnostic import (
    _is_marked_binary_difference,
)


def test_top_level_differing_binary_documents_is_accepted() -> None:
    payload = {
        "differing_binary_documents": ["lfdc", "reg_liva_250914"],
        "blocked_documents": ["lfdc", "reg_liva_250914"],
    }
    assert _is_marked_binary_difference(payload, "lfdc", None) is True


def test_unlisted_document_is_not_accepted() -> None:
    payload = {"differing_binary_documents": ["lfdc"]}
    assert (
        _is_marked_binary_difference(
            payload,
            "reg_liva_250914",
            None,
        )
        is False
    )
