from __future__ import annotations

from pathlib import Path

from app.services.semantic_source_residual_audit import (
    _find_source_line,
    _normalized_source_path,
)


def test_find_source_line_accepts_whitespace_normalization() -> None:
    source = "Artículo 10.-   Texto legal.\nOtro renglón."
    assert (
        _find_source_line(source, "Artículo 10.- Texto legal.")
        == "Artículo 10.-   Texto legal."
    )


def test_normalized_source_path_is_case_insensitive(tmp_path: Path) -> None:
    source = tmp_path / "LIVA.md"
    source.write_text("Artículo 1o.- Texto.", encoding="utf-8")
    assert _normalized_source_path(tmp_path, "liva") == source
