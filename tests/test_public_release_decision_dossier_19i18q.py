from __future__ import annotations

import pytest

from app.services.public_release_decision_dossier_19i18q import (
    EXPECTED_MODEL_ID,
    PublicationDecisionError,
    build_redistribution_matrix,
    build_temporal_policy,
    validate_model_license_evidence,
    validate_preproduction,
)


def valid_preproduction() -> dict[str, object]:
    return {
        "technical_chain_complete": True,
        "runtime_integrity_complete": True,
        "cold_start_complete": True,
        "embedding_dependency_complete": True,
        "publication_legal_acceptance": False,
        "temporal_validity_complete": False,
        "redistribution_human_review_required": True,
        "public_release_allowed": False,
        "git_push_allowed": False,
        "github_release_allowed": False,
        "render_deploy_allowed": False,
        "decision": "DO_NOT_PUBLISH",
    }


def valid_license() -> dict[str, object]:
    return {
        "model_id": EXPECTED_MODEL_ID,
        "license": "apache-2.0",
        "source_kind": "official_model_repository_metadata",
        "evidence_verified": True,
        "source_url": (
            "https://huggingface.co/sentence-transformers/"
            "paraphrase-multilingual-MiniLM-L12-v2"
        ),
    }


def test_preproduction_gate_is_accepted() -> None:
    validate_preproduction(valid_preproduction())


def test_preproduction_cannot_arrive_publishable() -> None:
    report = valid_preproduction()
    report["public_release_allowed"] = True
    with pytest.raises(PublicationDecisionError):
        validate_preproduction(report)


def test_model_license_evidence_is_accepted() -> None:
    validate_model_license_evidence(valid_license())


def test_model_license_wrong_license_fails_closed() -> None:
    evidence = valid_license()
    evidence["license"] = "unknown"
    with pytest.raises(PublicationDecisionError):
        validate_model_license_evidence(evidence)


def test_model_license_untrusted_url_fails_closed() -> None:
    evidence = valid_license()
    evidence["source_url"] = "https://example.invalid/model"
    with pytest.raises(PublicationDecisionError):
        validate_model_license_evidence(evidence)


def test_temporal_policy_guards_twelve_documents() -> None:
    policy = build_temporal_policy()
    assert policy["guarded_document_count"] == 12
    assert policy["human_acceptance_required"] is True
    assert policy["automatically_accepted"] is False


def test_redistribution_matrix_keeps_human_review() -> None:
    matrix = build_redistribution_matrix()
    assert len(matrix) == 14
    assert all(row["human_review_status"] == "pending" for row in matrix)
    assert all(
        row["automatic_redistribution_authorization"] is False
        for row in matrix
    )
