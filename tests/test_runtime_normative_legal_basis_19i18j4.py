from __future__ import annotations

import json
from pathlib import Path

from app.services.runtime_normative_legal_basis_gate import (
    evaluate_normative_legal_basis_gate,
)


def _write(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _legal_registry() -> dict[str, object]:
    return {
        "sources": [
            {"id": "mx_lfda_art14_viii"},
            {"id": "mx_dof_legal_notice"},
        ],
        "decision_policy": {
            "separate_review_documents": [
                "manual_derecho_fiscal_unam",
                "prodecon_contribuyente",
            ]
        },
    }


def test_exact_official_normative_text_is_only_candidate_not_promoted(
    tmp_path: Path,
) -> None:
    matrix = tmp_path / "matrix.json"
    evidence = tmp_path / "evidence.json"
    legal = tmp_path / "legal.json"
    _write(
        matrix,
        {
            "documents": [
                {
                    "document_id": "rmf_2026",
                    "content_conformant": True,
                    "runtime_to_local_pdf_verified": True,
                    "local_pdf_to_official_verified": True,
                    "publication_policy_status": "unknown_requires_review",
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
    _write(legal, _legal_registry())

    summary = evaluate_normative_legal_basis_gate(
        decision_matrix_path=matrix,
        evidence_registry_path=evidence,
        legal_basis_registry_path=legal,
    )

    assert summary.legal_basis_candidate_documents == ("rmf_2026",)
    assert summary.automatic_promotion_performed is False
    assert summary.public_release_allowed is False
    row = summary.documents[0]
    assert row.legal_basis_candidate_supported is True
    assert row.redistribution_policy_verified is False
    assert "redistribution_policy_not_verified" in row.blockers


def test_unreachable_official_source_remains_blocked(tmp_path: Path) -> None:
    matrix = tmp_path / "matrix.json"
    evidence = tmp_path / "evidence.json"
    legal = tmp_path / "legal.json"
    _write(
        matrix,
        {
            "documents": [
                {
                    "document_id": "cff",
                    "content_conformant": True,
                    "runtime_to_local_pdf_verified": True,
                    "local_pdf_to_official_verified": False,
                    "publication_policy_status": "unknown_requires_review",
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
    _write(legal, _legal_registry())

    summary = evaluate_normative_legal_basis_gate(
        decision_matrix_path=matrix,
        evidence_registry_path=evidence,
        legal_basis_registry_path=legal,
    )

    assert summary.legal_basis_candidate_documents == ()
    assert summary.official_provenance_pending_documents == ("cff",)
    row = summary.documents[0]
    assert row.legal_basis_candidate_supported is False
    assert "exact_official_provenance_not_verified" in row.blockers


def test_doctrine_and_orientation_remain_separate_review(tmp_path: Path) -> None:
    matrix = tmp_path / "matrix.json"
    evidence = tmp_path / "evidence.json"
    legal = tmp_path / "legal.json"
    _write(
        matrix,
        {
            "documents": [
                {
                    "document_id": "manual_derecho_fiscal_unam",
                    "content_conformant": False,
                    "runtime_to_local_pdf_verified": False,
                    "local_pdf_to_official_verified": False,
                    "publication_policy_status": "unknown_requires_review",
                },
                {
                    "document_id": "prodecon_contribuyente",
                    "content_conformant": False,
                    "runtime_to_local_pdf_verified": False,
                    "local_pdf_to_official_verified": False,
                    "publication_policy_status": "unknown_requires_review",
                },
            ]
        },
    )
    _write(
        evidence,
        {
            "documents": [
                {
                    "document_id": "manual_derecho_fiscal_unam",
                    "evidence_class": "separate_license_review_required",
                },
                {
                    "document_id": "prodecon_contribuyente",
                    "evidence_class": "separate_license_review_required",
                },
            ]
        },
    )
    _write(legal, _legal_registry())

    summary = evaluate_normative_legal_basis_gate(
        decision_matrix_path=matrix,
        evidence_registry_path=evidence,
        legal_basis_registry_path=legal,
    )

    assert summary.separate_review_documents == (
        "manual_derecho_fiscal_unam",
        "prodecon_contribuyente",
    )
    assert all(
        row.disposition == "separate_license_review_required"
        for row in summary.documents
    )


def test_resource_contains_current_authoritative_urls() -> None:
    payload = json.loads(
        Path(
            "app/resources/runtime_normative_legal_basis_19i18j4.json"
        ).read_text(encoding="utf-8")
    )
    urls = {
        item["id"]: item["url"]
        for item in payload["sources"]
    }
    assert urls["mx_lfda_art14_viii"] == (
        "https://www.diputados.gob.mx/LeyesBiblio/pdf/LFDA.pdf"
    )
    assert urls["mx_dof_legal_notice"] == (
        "https://dof.gob.mx/aviso_legal.html"
    )
    assert payload["decision_policy"]["automatic_publication_promotion"] is False
