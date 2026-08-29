from __future__ import annotations

from app.services.legal_identity_change_audit import (
    _detect_identity,
    _identity,
)


def test_detect_identity_normalizes_spaced_article_suffix() -> None:
    unit_type, label = _detect_identity("Artículo 18 -M.- Texto.")
    assert unit_type == "article"
    assert label == "Artículo 18 -M"


def test_identity_is_case_and_whitespace_insensitive() -> None:
    assert _identity("article", "Artículo 18-M") == _identity(
        "article",
        "  artículo   18-M ",
    )
