from __future__ import annotations

import json
from pathlib import Path

from app.services.normative_temporal_provenance_registry import (
    build_registry_from_verification,
    validate_fail_closed_registry,
)


def _write_report(path: Path) -> None:
    payload = {
        "records": [
            {
                "canonical_id": "cpeum",
                "source_path": "cpeum.md",
                "line_number": 100,
                "classification": "strong_entry_into_force",
                "explicit_date_signal": "31 de diciembre de 1999",
                "scope_classification": "amendment_specific_candidate",
                "scope_reason": "Decreto de reforma.",
            }
        ]
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_specific_amendment_is_blocked_from_document_wide_promotion(
    tmp_path: Path,
) -> None:
    report = tmp_path / "verification.json"
    _write_report(report)
    registry = build_registry_from_verification(
        verification_report_path=report
    )
    entry = registry.entries[0]
    assert entry.promotion_status == "blocked_scope_specific"
    assert entry.document_wide_applicable is False
    assert entry.effective_from is None
    assert entry.effective_to is None


def test_priority_documents_remain_fail_closed(tmp_path: Path) -> None:
    report = tmp_path / "verification.json"
    _write_report(report)
    registry = build_registry_from_verification(
        verification_report_path=report
    )
    gaps = {gap.canonical_id: gap for gap in registry.coverage_gaps}
    assert gaps["liva"].status == "unknown_fail_closed"
    assert gaps["cpeum"].status == "unknown_fail_closed"
    validate_fail_closed_registry(registry)


def test_registry_is_versioned(tmp_path: Path) -> None:
    report = tmp_path / "verification.json"
    _write_report(report)
    registry = build_registry_from_verification(
        verification_report_path=report
    )
    assert registry.schema_version == "1.0"
    assert registry.source_sprint == "19I.13"
