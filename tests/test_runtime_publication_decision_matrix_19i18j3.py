from __future__ import annotations

import json
from pathlib import Path

from app.services.runtime_publication_decision_matrix import (
    build_publication_decision_matrix,
)


def _write(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_decision_matrix_preserves_fail_closed_semantics(tmp_path: Path) -> None:
    safety = tmp_path / "safety.json"
    evidence = tmp_path / "evidence.json"
    content = tmp_path / "content.json"
    bridge = tmp_path / "bridge.json"
    official = tmp_path / "official.json"

    _write(
        safety,
        {
            "results": [
                {
                    "document_id": "cff",
                    "chunk_count": 10,
                    "redistribution_status": "unknown_requires_review",
                },
                {
                    "document_id": "manual",
                    "chunk_count": 5,
                    "redistribution_status": "unknown_requires_review",
                },
            ]
        },
    )
    _write(
        evidence,
        {
            "documents": [
                {
                    "document_id": "cff",
                    "evidence_class": "statutory_text_exclusion_candidate",
                },
                {
                    "document_id": "manual",
                    "evidence_class": "separate_license_review_required",
                },
            ]
        },
    )
    _write(
        content,
        {
            "documents": [
                {
                    "document_id": "cff",
                    "technical_conformity_passed": True,
                }
            ]
        },
    )
    _write(
        bridge,
        {
            "documents": [
                {
                    "document_id": "cff",
                    "bridge_verified": True,
                }
            ]
        },
    )
    _write(
        official,
        {
            "documents": [
                {
                    "document_id": "cff",
                    "official_provenance_verified": False,
                    "remote_sha256_values": [],
                    "fetch_errors": ["timeout"],
                }
            ]
        },
    )

    summary = build_publication_decision_matrix(
        safety_report_path=safety,
        evidence_registry_path=evidence,
        content_report_path=content,
        source_bridge_report_path=bridge,
        official_source_report_path=official,
    )

    assert summary.publication_ready_documents == ()
    assert summary.public_release_allowed is False
    assert summary.unresolved_external_evidence_documents == ("cff",)
    assert summary.separate_license_review_documents == ("manual",)

    cff = next(item for item in summary.documents if item.document_id == "cff")
    assert "external_official_source_evidence_pending" in cff.blockers
    assert "redistribution_policy_not_verified" in cff.blockers


def test_exact_official_match_still_requires_redistribution_policy(
    tmp_path: Path,
) -> None:
    safety = tmp_path / "safety.json"
    evidence = tmp_path / "evidence.json"
    content = tmp_path / "content.json"
    bridge = tmp_path / "bridge.json"
    official = tmp_path / "official.json"

    _write(
        safety,
        {
            "results": [
                {
                    "document_id": "rmf_2026",
                    "chunk_count": 10,
                    "redistribution_status": "unknown_requires_review",
                }
            ]
        },
    )
    _write(
        evidence,
        {
            "documents": [
                {
                    "document_id": "rmf_2026",
                    "evidence_class": "statutory_text_exclusion_candidate",
                }
            ]
        },
    )
    _write(
        content,
        {
            "documents": [
                {
                    "document_id": "rmf_2026",
                    "technical_conformity_passed": True,
                }
            ]
        },
    )
    _write(
        bridge,
        {
            "documents": [
                {
                    "document_id": "rmf_2026",
                    "bridge_verified": True,
                }
            ]
        },
    )
    _write(
        official,
        {
            "documents": [
                {
                    "document_id": "rmf_2026",
                    "official_provenance_verified": True,
                    "remote_sha256_values": ["a" * 64],
                    "fetch_errors": [],
                }
            ]
        },
    )

    summary = build_publication_decision_matrix(
        safety_report_path=safety,
        evidence_registry_path=evidence,
        content_report_path=content,
        source_bridge_report_path=bridge,
        official_source_report_path=official,
    )

    row = summary.documents[0]
    assert row.local_pdf_to_official_verified is True
    assert row.publication_ready is False
    assert row.blockers == ("redistribution_policy_not_verified",)


def test_upstream_report_field_contracts_are_supported(tmp_path: Path) -> None:
    safety = tmp_path / "safety.json"
    evidence = tmp_path / "evidence.json"
    content = tmp_path / "content.json"
    bridge = tmp_path / "bridge.json"
    official = tmp_path / "official.json"

    _write(
        safety,
        {
            "results": [
                {
                    "document_id": "cff",
                    "chunk_count": 3,
                    "text_bytes": 99,
                    "redistribution_status": "public_redistribution_verified",
                    "evidence": "fixture",
                    "publishable": True,
                }
            ]
        },
    )
    _write(
        evidence,
        {
            "documents": [
                {
                    "document_id": "cff",
                    "evidence_class": "statutory_text_exclusion_candidate",
                }
            ]
        },
    )
    _write(
        content,
        {
            "documents": [
                {
                    "document_id": "cff",
                    "technical_conformity_passed": True,
                }
            ]
        },
    )
    _write(
        bridge,
        {
            "documents": [
                {
                    "document_id": "cff",
                    "bridge_verified": True,
                }
            ]
        },
    )
    _write(
        official,
        {
            "documents": [
                {
                    "document_id": "cff",
                    "official_provenance_verified": True,
                    "remote_sha256_values": ["b" * 64],
                    "fetch_errors": [],
                }
            ]
        },
    )

    summary = build_publication_decision_matrix(
        safety_report_path=safety,
        evidence_registry_path=evidence,
        content_report_path=content,
        source_bridge_report_path=bridge,
        official_source_report_path=official,
    )

    assert summary.publication_ready_documents == ("cff",)
    assert summary.public_release_allowed is True
    assert summary.documents[0].runtime_chunks == 3


def test_script_uses_actual_19i18g_report_path() -> None:
    script = Path(
        "scripts/build_runtime_publication_decision_matrix_19i18j3.py"
    ).read_text(encoding="utf-8")
    assert (
        "reports/sprint19I18G/runtime_publication_content_conformity.json"
        in script
    )
    assert "runtime_publication_content.json" not in script
