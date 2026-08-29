from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.runtime_browser_official_download_plan import (
    build_browser_download_plan,
)
from app.services.runtime_official_source_audit import OfficialSourceAuditError


def _write_registry(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "document_id": "cff",
                        "candidate_urls": [
                            "https://www.diputados.gob.mx/LeyesBiblio/pdf/CFF.pdf"
                        ],
                    },
                    {
                        "document_id": "liva",
                        "candidate_urls": [
                            "https://www.diputados.gob.mx/LeyesBiblio/pdf/LIVA.pdf"
                        ],
                    },
                    {
                        "document_id": "rmf_2026",
                        "candidate_urls": [
                            "https://dof.gob.mx/2025/SHCP/SHCP_281225_01.pdf"
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )


def test_plan_filters_authority_and_marks_verified(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    manifest = tmp_path / "manifest.json"
    bridge = tmp_path / "bridge.json"
    _write_registry(registry)
    manifest.write_text(
        json.dumps({"documents": [{"document_id": "cff"}]}),
        encoding="utf-8",
    )
    bridge.write_text(
        json.dumps({"exact_binary_verified_documents": ["cff"]}),
        encoding="utf-8",
    )

    summary = build_browser_download_plan(
        candidate_registry_path=registry,
        authority_host="www.diputados.gob.mx",
        browser_manifest_path=manifest,
        browser_bridge_report_path=bridge,
    )

    assert summary.candidate_documents == 2
    assert summary.exact_binary_verified_documents == ("cff",)
    assert summary.pending_download_documents == ("liva",)
    assert {item.document_id for item in summary.items} == {"cff", "liva"}


def test_imported_but_not_verified_has_distinct_status(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    manifest = tmp_path / "manifest.json"
    bridge = tmp_path / "bridge.json"
    _write_registry(registry)
    manifest.write_text(
        json.dumps({"documents": [{"document_id": "liva"}]}),
        encoding="utf-8",
    )
    bridge.write_text(
        json.dumps({"exact_binary_verified_documents": []}),
        encoding="utf-8",
    )

    summary = build_browser_download_plan(
        candidate_registry_path=registry,
        authority_host="www.diputados.gob.mx",
        browser_manifest_path=manifest,
        browser_bridge_report_path=bridge,
    )

    assert summary.imported_unverified_documents == ("liva",)
    item = next(item for item in summary.items if item.document_id == "liva")
    assert item.status == "imported_pending_bridge_audit"


def test_unexpected_verified_document_is_rejected(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    bridge = tmp_path / "bridge.json"
    _write_registry(registry)
    bridge.write_text(
        json.dumps({"exact_binary_verified_documents": ["rmf_2026"]}),
        encoding="utf-8",
    )

    with pytest.raises(OfficialSourceAuditError):
        build_browser_download_plan(
            candidate_registry_path=registry,
            authority_host="www.diputados.gob.mx",
            browser_bridge_report_path=bridge,
        )


def test_import_command_uses_expected_filename(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    _write_registry(registry)

    summary = build_browser_download_plan(
        candidate_registry_path=registry,
        authority_host="www.diputados.gob.mx",
    )

    liva = next(item for item in summary.items if item.document_id == "liva")
    assert liva.expected_filename == "liva.pdf"
    assert "--document-id liva" in liva.import_command
    assert "liva.pdf" in liva.import_command
