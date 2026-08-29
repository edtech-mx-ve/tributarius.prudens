from __future__ import annotations

import json
from pathlib import Path

from app.services.runtime_browser_acquisition_readiness import (
    build_acquisition_readiness,
)


def _write_plan(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "document_id": "cff",
                        "status": "exact_binary_verified",
                        "source_url": (
                            "https://www.diputados.gob.mx/"
                            "LeyesBiblio/pdf/CFF.pdf"
                        ),
                    },
                    {
                        "document_id": "cpeum",
                        "status": "pending_browser_download",
                        "source_url": (
                            "https://www.diputados.gob.mx/"
                            "LeyesBiblio/pdf/CPEUM.pdf"
                        ),
                    },
                    {
                        "document_id": "liva",
                        "status": "pending_browser_download",
                        "source_url": (
                            "https://www.diputados.gob.mx/"
                            "LeyesBiblio/pdf/LIVA.pdf"
                        ),
                    },
                ]
            }
        ),
        encoding="utf-8",
    )


def test_marks_existing_manifest_evidence_as_available(tmp_path: Path) -> None:
    plan = tmp_path / "plan.json"
    _write_plan(plan)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"documents": [{"document_id": "cpeum"}]}),
        encoding="utf-8",
    )
    downloads = tmp_path / "downloads"
    downloads.mkdir()

    report = build_acquisition_readiness(
        downloads_dir=downloads,
        plan_path=plan,
        evidence_manifest_path=manifest,
        report_path=tmp_path / "report.json",
    )

    assert report["already_available_documents"] == ["cff", "cpeum"]
    assert report["pending_or_invalid_documents"] == ["liva"]
    assert report["batch_import_allowed"] is False


def test_ready_pdf_is_hashed(tmp_path: Path) -> None:
    plan = tmp_path / "plan.json"
    _write_plan(plan)
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    (downloads / "cpeum.pdf").write_bytes(b"%PDF-1.7\ncpeum")
    (downloads / "liva.pdf").write_bytes(b"%PDF-1.7\nliva")

    report = build_acquisition_readiness(
        downloads_dir=downloads,
        plan_path=plan,
        evidence_manifest_path=tmp_path / "missing.json",
        report_path=tmp_path / "report.json",
    )

    assert report["ready_for_batch_import_documents"] == ["cpeum", "liva"]
    assert report["pending_or_invalid_documents"] == []
    assert report["batch_import_allowed"] is True


def test_invalid_file_is_not_ready(tmp_path: Path) -> None:
    plan = tmp_path / "plan.json"
    _write_plan(plan)
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    (downloads / "cpeum.pdf").write_bytes(b"%PDF-1.7\ncpeum")
    (downloads / "liva.pdf").write_text("html", encoding="utf-8")

    report = build_acquisition_readiness(
        downloads_dir=downloads,
        plan_path=plan,
        evidence_manifest_path=tmp_path / "missing.json",
        report_path=tmp_path / "report.json",
    )

    assert "liva" in report["pending_or_invalid_documents"]
    assert report["batch_import_allowed"] is False


def test_report_is_written(tmp_path: Path) -> None:
    plan = tmp_path / "plan.json"
    _write_plan(plan)
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    report_path = tmp_path / "nested" / "report.json"

    build_acquisition_readiness(
        downloads_dir=downloads,
        plan_path=plan,
        evidence_manifest_path=tmp_path / "missing.json",
        report_path=report_path,
    )

    assert report_path.is_file()
