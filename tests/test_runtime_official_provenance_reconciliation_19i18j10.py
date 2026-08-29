from __future__ import annotations

import json
from pathlib import Path

from app.services.runtime_official_provenance_reconciliation import (
    CAMARA_DOCUMENTS,
    NORMATIVE_DOCUMENTS,
    reconcile_official_provenance,
)


def _write(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _fixture_paths(tmp_path: Path, *, missing_camara: str | None = None) -> dict[str, Path]:
    browser_exact = [
        document_id
        for document_id in CAMARA_DOCUMENTS
        if document_id != missing_camara
    ]
    browser = _write(
        tmp_path / "browser.json",
        {"exact_binary_verified_documents": browser_exact},
    )
    online = _write(
        tmp_path / "online.json",
        {
            "documents": [
                {
                    "document_id": "rmf_2026",
                    "status": "exact_binary_official_source_verified",
                }
            ]
        },
    )
    local = _write(
        tmp_path / "local.json",
        {
            "documents": [
                {"document_id": doc, "bridge_verified": True}
                for doc in NORMATIVE_DOCUMENTS
            ]
        },
    )
    conformity = _write(
        tmp_path / "conformity.json",
        {
            "documents": [
                {"document_id": doc, "technical_conformity_passed": True}
                for doc in NORMATIVE_DOCUMENTS
            ]
        },
    )
    legal = _write(
        tmp_path / "legal.json",
        {
            "documents": [
                {
                    "document_id": doc,
                    "disposition": "legal_basis_candidate_supported",
                }
                for doc in NORMATIVE_DOCUMENTS
            ]
        },
    )
    policy = _write(
        tmp_path / "policy.json",
        {
            "documents": [
                {
                    "document_id": doc,
                    "publication_policy_status": "unknown_requires_review",
                }
                for doc in (*NORMATIVE_DOCUMENTS, "manual_unam", "prodecon")
            ]
        },
    )
    temporal = _write(
        tmp_path / "temporal.json",
        {
            "documents": [
                {"document_id": doc, "status": "unknown_fail_closed"}
                for doc in NORMATIVE_DOCUMENTS
            ]
        },
    )
    return {
        "browser_bridge_path": browser,
        "online_provenance_path": online,
        "local_bridge_path": local,
        "conformity_path": conformity,
        "legal_basis_path": legal,
        "publication_policy_path": policy,
        "temporal_registry_path": temporal,
        "output_path": tmp_path / "out.json",
    }


def test_all_fourteen_normative_documents_can_have_exact_provenance(
    tmp_path: Path,
) -> None:
    report = reconcile_official_provenance(**_fixture_paths(tmp_path))
    assert report["official_provenance_exact_normative_count"] == 14
    assert report["official_provenance_complete_for_normative_corpus"] is True
    assert report["public_release_allowed"] is False


def test_missing_one_camara_document_fails_closed(tmp_path: Path) -> None:
    report = reconcile_official_provenance(
        **_fixture_paths(tmp_path, missing_camara="liva")
    )
    assert report["official_provenance_exact_normative_count"] == 13
    assert report["official_provenance_complete_for_normative_corpus"] is False
    row = next(
        item for item in report["documents"] if item["document_id"] == "liva"
    )
    assert "official_binary_provenance_not_verified" in row["blockers"]


def test_redistribution_and_temporal_controls_remain_independent(
    tmp_path: Path,
) -> None:
    report = reconcile_official_provenance(**_fixture_paths(tmp_path))
    row = next(
        item for item in report["documents"] if item["document_id"] == "cff"
    )
    assert row["official_provenance_verified"] is True
    assert "public_redistribution_not_verified" in row["blockers"]
    assert "document_wide_temporal_validity_not_verified" in row["blockers"]
    assert row["publication_ready"] is False


def test_unam_and_prodecon_require_separate_review(tmp_path: Path) -> None:
    report = reconcile_official_provenance(**_fixture_paths(tmp_path))
    rows = {
        item["document_id"]: item
        for item in report["documents"]
    }
    for document_id in ("manual_unam", "prodecon"):
        assert rows[document_id]["publication_ready"] is False
        assert rows[document_id]["legal_basis_status"] == (
            "separate_license_review_required"
        )
