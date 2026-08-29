from __future__ import annotations

import pytest

from app.services.public_release_preproduction_gate_19i18p import (
    EXPECTED_CANDIDATE_SHA256,
    EXPECTED_CANONICAL_SHA256,
    EXPECTED_DIMENSION,
    EXPECTED_FAISS_NTOTAL,
    EXPECTED_MODEL_ID,
    PreproductionGateError,
    validate_chain,
)


def reports() -> tuple[dict[str, object], ...]:
    report_19l = {
        "normative_document_count": 14,
        "provenance_complete": True,
        "temporal_fail_closed_complete": True,
        "temporal_validity_complete": False,
        "redistribution_human_review_required": True,
        "legal_local_acceptance": True,
        "publication_legal_acceptance": False,
        "public_release_allowed": False,
        "git_push_allowed": False,
        "github_release_allowed": False,
        "render_deploy_allowed": False,
    }
    report_19m = {
        "candidate_only": True,
        "zip_sha256": EXPECTED_CANDIDATE_SHA256,
        "technical_release_candidate_acceptance": True,
        "runtime_integrity_preserved_after_sanitization": True,
        "blocked_document_identity_absent": True,
        "secret_scan_passed": True,
        "absolute_private_path_scan_passed": True,
        "forbidden_extension_scan_passed": True,
        "deterministic_zip_verified": True,
        "publication_legal_acceptance": False,
        "temporal_validity_complete": False,
        "redistribution_human_review_required": True,
        "public_release_allowed": False,
        "git_push_allowed": False,
        "github_release_allowed": False,
        "render_deploy_allowed": False,
    }
    report_19n = {
        "candidate_zip_sha256": EXPECTED_CANDIDATE_SHA256,
        "canonical_sha256": EXPECTED_CANONICAL_SHA256,
        "manifest_integrity_passed": True,
        "zip_path_safety_passed": True,
        "runtime_loaded_from_extracted_candidate_only": True,
        "source_runtime_path_not_used": True,
        "blocked_document_identity_absent": True,
        "cold_start_acceptance": True,
        "embedding_model_bundled": False,
        "embedding_model_external_dependency": True,
        "semantic_query_embedding_cold_start_proven": False,
        "deployment_sufficiency_acceptance": False,
        "publication_legal_acceptance": False,
        "temporal_validity_complete": False,
        "redistribution_human_review_required": True,
        "public_release_allowed": False,
        "git_push_allowed": False,
        "github_release_allowed": False,
        "render_deploy_allowed": False,
    }
    report_19o = {
        "candidate_zip_sha256": EXPECTED_CANDIDATE_SHA256,
        "canonical_sha256": EXPECTED_CANONICAL_SHA256,
        "model_id": EXPECTED_MODEL_ID,
        "fresh_unauthenticated_model_fetch_passed": True,
        "offline_model_reload_passed": True,
        "semantic_query_embedding_cold_start_proven": True,
        "embedding_dimension": EXPECTED_DIMENSION,
        "faiss_dimension": EXPECTED_DIMENSION,
        "faiss_ntotal": EXPECTED_FAISS_NTOTAL,
        "runtime_loaded_from_candidate_only": True,
        "source_corpus_not_used": True,
        "commercial_api_required": False,
        "api_key_required": False,
        "credit_card_required": False,
        "deployment_sufficiency_acceptance": True,
        "model_weights_in_public_candidate": False,
        "model_cache_local_build_artifact_only": True,
        "model_license_review_required": True,
        "publication_legal_acceptance": False,
        "temporal_validity_complete": False,
        "redistribution_human_review_required": True,
        "public_release_allowed": False,
        "git_push_allowed": False,
        "github_release_allowed": False,
        "render_deploy_allowed": False,
    }
    return report_19l, report_19m, report_19n, report_19o


def test_valid_chain_closes_technical_preproduction() -> None:
    report_19l, report_19m, report_19n, report_19o = reports()
    result = validate_chain(
        report_19l=report_19l,
        report_19m=report_19m,
        report_19n=report_19n,
        report_19o=report_19o,
    )
    assert result.technical_chain_complete
    assert result.embedding_dependency_complete
    assert not result.public_release_allowed


@pytest.mark.parametrize(
    ("position", "key", "bad_value"),
    [
        (0, "provenance_complete", False),
        (1, "secret_scan_passed", False),
        (2, "cold_start_acceptance", False),
        (3, "deployment_sufficiency_acceptance", False),
        (3, "faiss_dimension", 768),
    ],
)
def test_chain_fails_closed(
    position: int,
    key: str,
    bad_value: object,
) -> None:
    values = list(reports())
    values[position][key] = bad_value
    with pytest.raises(PreproductionGateError):
        validate_chain(
            report_19l=values[0],
            report_19m=values[1],
            report_19n=values[2],
            report_19o=values[3],
        )
