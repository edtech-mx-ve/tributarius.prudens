from __future__ import annotations

from pathlib import Path

from app.services.runtime_publication_evidence_audit import (
    audit_publication_evidence,
)


def test_real_evidence_registry_covers_policy_without_promotion() -> None:
    summary = audit_publication_evidence(
        policy_path=Path(
            "app/resources/runtime_publication_policy_19i18e.json"
        ),
        evidence_path=Path(
            "app/resources/runtime_publication_evidence_19i18f.json"
        ),
    )

    assert summary.policy_documents == 16
    assert summary.evidence_documents == 16
    assert summary.statutory_candidates == 14
    assert summary.separate_license_review == 2
    assert summary.missing_evidence_documents == ()
    assert summary.extra_evidence_documents == ()
    assert summary.promotion_ready_documents == ()
