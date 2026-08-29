from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

EXPECTED_CANDIDATE_SHA256 = (
    "4766b49014c5f40aa509b325ddb7268ca7032348559937d2ebae74b0dcefe360"
)
EXPECTED_CANONICAL_SHA256 = (
    "7b4bb564cdfbd849a961790bcfad938d09369ffc41edc2de4cedce1cab2c49b0"
)
EXPECTED_MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EXPECTED_DIMENSION = 384
EXPECTED_FAISS_NTOTAL = 26107
EXPECTED_NORMATIVE_DOCUMENTS = 14


class PreproductionGateError(RuntimeError):
    """Raised when a required upstream acceptance artifact is inconsistent."""


@dataclass(frozen=True)
class GateResult:
    technical_chain_complete: bool
    runtime_integrity_complete: bool
    cold_start_complete: bool
    embedding_dependency_complete: bool
    publication_legal_acceptance: bool
    temporal_validity_complete: bool
    redistribution_human_review_required: bool
    public_release_allowed: bool
    git_push_allowed: bool
    github_release_allowed: bool
    render_deploy_allowed: bool


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PreproductionGateError(f"No se pudo leer JSON: {path}") from exc
    if not isinstance(value, dict):
        raise PreproductionGateError(f"Objeto JSON esperado: {path}")
    return value


def require(report: dict[str, Any], expected: dict[str, Any], label: str) -> None:
    mismatches = {
        key: {"actual": report.get(key), "expected": value}
        for key, value in expected.items()
        if report.get(key) != value
    }
    if mismatches:
        raise PreproductionGateError(f"{label} inconsistente: {mismatches}")


def validate_chain(
    *,
    report_19l: dict[str, Any],
    report_19m: dict[str, Any],
    report_19n: dict[str, Any],
    report_19o: dict[str, Any],
) -> GateResult:
    require(
        report_19l,
        {
            "normative_document_count": EXPECTED_NORMATIVE_DOCUMENTS,
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
        },
        "19L",
    )
    require(
        report_19m,
        {
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
        },
        "19M",
    )
    require(
        report_19n,
        {
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
        },
        "19N",
    )
    require(
        report_19o,
        {
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
        },
        "19O",
    )

    return GateResult(
        technical_chain_complete=True,
        runtime_integrity_complete=True,
        cold_start_complete=True,
        embedding_dependency_complete=True,
        publication_legal_acceptance=False,
        temporal_validity_complete=False,
        redistribution_human_review_required=True,
        public_release_allowed=False,
        git_push_allowed=False,
        github_release_allowed=False,
        render_deploy_allowed=False,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def execute(
    *,
    report_19l_path: Path,
    report_19m_path: Path,
    report_19n_path: Path,
    report_19o_path: Path,
    candidate_zip: Path,
    output_path: Path,
) -> dict[str, Any]:
    if not candidate_zip.is_file():
        raise PreproductionGateError(f"Candidato ausente: {candidate_zip}")
    actual_sha = sha256_file(candidate_zip)
    if actual_sha != EXPECTED_CANDIDATE_SHA256:
        raise PreproductionGateError(
            f"SHA candidato inesperado: {actual_sha}"
        )

    result = validate_chain(
        report_19l=load_json(report_19l_path),
        report_19m=load_json(report_19m_path),
        report_19n=load_json(report_19n_path),
        report_19o=load_json(report_19o_path),
    )
    payload: dict[str, Any] = {
        "sprint": "19I.18P",
        "status": "technical_preproduction_complete_publication_blocked",
        "candidate_zip_sha256": actual_sha,
        "canonical_sha256": EXPECTED_CANONICAL_SHA256,
        **asdict(result),
        "remaining_blockers": [
            "redistribution_human_review",
            "temporal_validity_completion_or_explicit_fail_closed_release_policy",
            "embedding_model_license_review",
        ],
        "automatic_publication_performed": False,
        "decision": "DO_NOT_PUBLISH",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload
