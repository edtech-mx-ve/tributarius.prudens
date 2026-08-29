from __future__ import annotations

from rag.chunking.legal_structurer import _detect_boundary


def test_generic_markdown_heading_is_not_legal_article_boundary() -> None:
    assert _detect_boundary("### Nota de reforma", "legal_article") is None


def test_reference_like_line_is_not_legal_article_boundary() -> None:
    assert (
        _detect_boundary(
            "Artículo 31-A, primer párrafo, inciso d) de este Código",
            "legal_article",
        )
        is None
    )


def test_real_article_heading_is_boundary_for_legal_profile() -> None:
    boundary = _detect_boundary("Artículo 18-M.- Texto.", "legal_article")
    assert boundary is not None
    assert boundary[0].value == "article"
    assert boundary[1] == "Artículo 18-M"
