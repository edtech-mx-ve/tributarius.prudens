from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.runtime_selective_rebuild_plan import (
    SelectiveRebuildPlanError,
    build_selective_rebuild_plan,
)


def _write_report(
    path: Path,
    material: list[str],
) -> Path:
    documents = []
    for document_id in ("lfdc", "reg_liva_250914"):
        documents.append(
            {
                "document_id": document_id,
                "classification": "material_textual_difference_detected",
                "text_similarity": 0.99,
                "official_pdf": f"official/{document_id}.pdf",
                "local_pdf": f"local/{document_id}.pdf",
                "official": {"sha256": "a" * 64},
                "local": {"sha256": "b" * 64},
            }
        )
    path.write_text(
        json.dumps(
            {
                "sprint": "19I.18J.11",
                "material_textual_difference_documents": material,
                "documents": documents,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_builds_plan_for_two_real_targets(tmp_path: Path) -> None:
    source = _write_report(
        tmp_path / "j11.json",
        ["lfdc", "reg_liva_250914"],
    )
    report = build_selective_rebuild_plan(
        differential_report_path=source,
        output_path=tmp_path / "out.json",
    )
    assert report["target_documents"] == ["lfdc", "reg_liva_250914"]
    assert report["target_count"] == 2
    assert report["rebuild_executed"] is False
    assert report["public_release_allowed"] is False


def test_rejects_unexpected_document(tmp_path: Path) -> None:
    source = _write_report(tmp_path / "j11.json", ["cff"])
    with pytest.raises(SelectiveRebuildPlanError):
        build_selective_rebuild_plan(
            differential_report_path=source,
            output_path=tmp_path / "out.json",
        )


def test_rejects_empty_material_set(tmp_path: Path) -> None:
    source = _write_report(tmp_path / "j11.json", [])
    with pytest.raises(SelectiveRebuildPlanError):
        build_selective_rebuild_plan(
            differential_report_path=source,
            output_path=tmp_path / "out.json",
        )


def test_plan_requires_atomic_index_and_regression(tmp_path: Path) -> None:
    source = _write_report(tmp_path / "j11.json", ["lfdc"])
    report = build_selective_rebuild_plan(
        differential_report_path=source,
        output_path=tmp_path / "out.json",
    )
    assert report["requires_backup_before_mutation"] is True
    assert report["requires_atomic_index_replacement"] is True
    assert report["requires_post_rebuild_regression"] is True
