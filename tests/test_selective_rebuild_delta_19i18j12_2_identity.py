from __future__ import annotations

from pathlib import Path

import pytest

from app.services.selective_rebuild_delta import (
    SelectiveRebuildDeltaError,
    _find_normalized_for_document,
    _key,
)


def test_key_normalizes_spaces_case_accents_and_punctuation() -> None:
    assert _key("Manual Derecho Fiscal") == "manual_derecho_fiscal"
    assert _key("Reg_LIVA_250914") == "reg_liva_250914"
    assert _key("Constitución-Fiscal") == "constitucion_fiscal"


def test_manifest_title_resolves_unam_descriptive_filename(
    tmp_path: Path,
) -> None:
    root = tmp_path / "normalized"
    root.mkdir()
    expected = root / "Manual Derecho Fiscal.md"
    expected.write_text("manual", encoding="utf-8")

    resolved = _find_normalized_for_document(
        root,
        "manual_derecho_fiscal_unam",
        {
            "filename": "Manual Derecho Fiscal.pdf",
            "title": "Manual Derecho Fiscal",
        },
    )
    assert resolved == expected


def test_normalized_identity_does_not_use_substring(tmp_path: Path) -> None:
    root = tmp_path / "normalized"
    root.mkdir()
    (root / "reg_cff.md").write_text("reg", encoding="utf-8")

    with pytest.raises(SelectiveRebuildDeltaError):
        _find_normalized_for_document(root, "cff", {})
