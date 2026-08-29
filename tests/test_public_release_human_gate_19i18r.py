from __future__ import annotations

import pytest

from app.services.public_release_human_gate_19i18r import (
    HumanReleaseDecisionError,
    validate_dossier,
    validate_human_decision,
)


def valid_dossier() -> dict[str, object]:
    return {
        "technical_preproduction_complete": True,
        "model_license_metadata_verified": True,
        "model_license_review_required": False,
        "temporal_fail_closed_policy_ready": True,
        "temporal_policy_human_acceptance_required": True,
        "redistribution_human_review_required": True,
        "publication_legal_acceptance": False,
        "public_release_allowed": False,
        "git_push_allowed": False,
        "github_release_allowed": False,
        "render_deploy_allowed": False,
        "decision": "DO_NOT_PUBLISH",
        "redistribution_matrix": [{} for _ in range(14)],
    }


def valid_decision() -> dict[str, object]:
    return {
        "temporal_fail_closed_release_policy": "APPROVED",
        "normative_text_redistribution": "APPROVED",
        "scope": "public_normative_runtime_only",
        "doctrine_editorial_content_included": False,
        "acknowledges_temporal_fail_closed_constraints": True,
        "acknowledges_official_text_conformity_requirement": True,
        "reviewer": "project_owner",
        "review_date": "2026-08-29",
        "decision_statement": "A. Acepto ambas decisiones.",
    }


def test_valid_dossier() -> None:
    validate_dossier(valid_dossier())


def test_dossier_cannot_be_preapproved() -> None:
    dossier = valid_dossier()
    dossier["public_release_allowed"] = True
    with pytest.raises(HumanReleaseDecisionError):
        validate_dossier(dossier)


def test_explicit_human_approval() -> None:
    validate_human_decision(valid_decision())


def test_temporal_rejection_fails_closed() -> None:
    decision = valid_decision()
    decision["temporal_fail_closed_release_policy"] = "REJECTED"
    with pytest.raises(HumanReleaseDecisionError):
        validate_human_decision(decision)


def test_redistribution_rejection_fails_closed() -> None:
    decision = valid_decision()
    decision["normative_text_redistribution"] = "REJECTED"
    with pytest.raises(HumanReleaseDecisionError):
        validate_human_decision(decision)


def test_doctrine_inclusion_fails_closed() -> None:
    decision = valid_decision()
    decision["doctrine_editorial_content_included"] = True
    with pytest.raises(HumanReleaseDecisionError):
        validate_human_decision(decision)


def test_missing_reviewer_fails_closed() -> None:
    decision = valid_decision()
    decision["reviewer"] = ""
    with pytest.raises(HumanReleaseDecisionError):
        validate_human_decision(decision)


def test_invalid_date_fails_closed() -> None:
    decision = valid_decision()
    decision["review_date"] = "29/08/2026"
    with pytest.raises(HumanReleaseDecisionError):
        validate_human_decision(decision)
