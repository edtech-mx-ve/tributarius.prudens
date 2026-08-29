from __future__ import annotations

from pathlib import Path

import pytest

from app.services.selective_rebuild_delta import (
    SelectiveRebuildDeltaError,
    _find_normalized_for_document,
)


def test_exact_stem_wins_over_substring_collision(tmp_path: Path) -> None:
    root = tmp_path / "normalized"
    root.mkdir()
    expected = root / "cff.md"
    expected.write_text("cff", encoding="utf-8")
    (root / "reg_cff.md").write_text("reg", encoding="utf-8")

    resolved = _find_normalized_for_document(root, "cff", {})
    assert resolved == expected


def test_filename_stem_resolves_when_canonical_id_differs(tmp_path: Path) -> None:
    root = tmp_path / "normalized"
    root.mkdir()
    expected = root / "LFDC.md"
    expected.write_text("lfdc", encoding="utf-8")

    resolved = _find_normalized_for_document(
        root,
        "lfdc",
        {"filename": "LFDC.pdf"},
    )
    assert resolved == expected


def test_ambiguous_exact_stem_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "normalized"
    (root / "a").mkdir(parents=True)
    (root / "b").mkdir(parents=True)
    (root / "a" / "cff.md").write_text("a", encoding="utf-8")
    (root / "b" / "CFF.md").write_text("b", encoding="utf-8")

    with pytest.raises(SelectiveRebuildDeltaError):
        _find_normalized_for_document(root, "cff", {})
