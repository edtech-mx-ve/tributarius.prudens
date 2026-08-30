from app.services.public_explanation_integrity_19s_r16f import (
    build_explanation_integrity,
    explanation_integrity_status,
    reconcile_public_explanation_payload,
)


def test_not_generated_when_explanation_missing() -> None:
    result = {
        "requires_human_review": True,
        "evidence": [],
        "applicable_normative_refs": [],
    }
    assert explanation_integrity_status(result) == "not_generated"


def test_review_required_with_evidence_and_no_applicable_norm() -> None:
    result = {
        "explanation": "Respuesta basada en evidencia recuperada.",
        "requires_human_review": True,
        "evidence": [{"ref_id": "x"}],
        "applicable_normative_refs": [],
    }
    integrity = build_explanation_integrity(result)
    assert integrity["status"] == "evidence_only_review_required"
    assert integrity["evidence_count"] == 1
    assert integrity["applicable_normative_ref_count"] == 0
    assert integrity["llm_authority"] == "none"


def test_grounded_applicable_norm_requires_no_review() -> None:
    result = {
        "explanation": "Explicación.",
        "requires_human_review": False,
        "evidence": [{"ref_id": "x"}],
        "applicable_normative_refs": [{"ref_id": "n1"}],
    }
    assert explanation_integrity_status(result) == "grounded_applicable_norm"


def test_ungrounded_explanation_is_never_promoted() -> None:
    result = {
        "explanation": "Explicación.",
        "requires_human_review": False,
        "evidence": [],
        "applicable_normative_refs": [],
    }
    assert explanation_integrity_status(result) == "ungrounded"


def test_reconcile_is_non_mutating_and_preserves_explanation() -> None:
    payload = {
        "result": {
            "explanation": "Texto original.",
            "requires_human_review": True,
            "evidence": [{"ref_id": "x"}],
            "applicable_normative_refs": [],
        }
    }

    reconciled = reconcile_public_explanation_payload(payload)

    assert payload["result"].get("explanation_integrity") is None
    assert reconciled["result"]["explanation"] == "Texto original."
    assert (
        reconciled["result"]["explanation_integrity"]["status"]
        == "evidence_only_review_required"
    )
