from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

EXPECTED_MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EXPECTED_MODEL_LICENSE = "apache-2.0"
EXPECTED_CANONICAL_SHA256 = (
    "7b4bb564cdfbd849a961790bcfad938d09369ffc41edc2de4cedce1cab2c49b0"
)

NORMATIVE_DOCUMENTS = (
    "cff",
    "cpeum",
    "lfdc",
    "lfisan",
    "lfpca",
    "lieps",
    "lif_2026",
    "lisr",
    "liva",
    "lotfja",
    "reg_cff",
    "reg_lisr_060516",
    "reg_liva_250914",
    "rmf_2026",
)
TEMPORAL_EVIDENCE_REGISTERED = ("lif_2026", "rmf_2026")
TEMPORAL_FAIL_CLOSED = tuple(
    item for item in NORMATIVE_DOCUMENTS if item not in TEMPORAL_EVIDENCE_REGISTERED
)


class PublicationDecisionError(RuntimeError):
    """Fail-closed error for publication-decision consolidation."""


@dataclass(frozen=True)
class Decision:
    technical_preproduction_complete: bool
    model_license_metadata_verified: bool
    model_license_review_required: bool
    temporal_fail_closed_policy_ready: bool
    temporal_policy_human_acceptance_required: bool
    redistribution_human_review_required: bool
    publication_legal_acceptance: bool
    public_release_allowed: bool
    git_push_allowed: bool
    github_release_allowed: bool
    render_deploy_allowed: bool
    decision: str


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicationDecisionError(f"No se pudo leer JSON: {path}") from exc
    if not isinstance(value, dict):
        raise PublicationDecisionError(f"Objeto JSON esperado: {path}")
    return value


def require(report: dict[str, Any], expected: dict[str, Any], label: str) -> None:
    mismatches = {
        key: {"actual": report.get(key), "expected": expected_value}
        for key, expected_value in expected.items()
        if report.get(key) != expected_value
    }
    if mismatches:
        raise PublicationDecisionError(f"{label} inconsistente: {mismatches}")


def validate_preproduction(report: dict[str, Any]) -> None:
    require(
        report,
        {
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
        },
        "19P",
    )


def validate_model_license_evidence(evidence: dict[str, Any]) -> None:
    require(
        evidence,
        {
            "model_id": EXPECTED_MODEL_ID,
            "license": EXPECTED_MODEL_LICENSE,
            "source_kind": "official_model_repository_metadata",
            "evidence_verified": True,
        },
        "licencia-modelo",
    )
    source_url = evidence.get("source_url")
    if not isinstance(source_url, str) or not source_url.startswith(
        "https://huggingface.co/sentence-transformers/"
    ):
        raise PublicationDecisionError("URL de evidencia de modelo no autorizada")


def build_temporal_policy() -> dict[str, Any]:
    return {
        "policy_id": "temporal_fail_closed_release_v1",
        "known_temporal_documents": list(TEMPORAL_EVIDENCE_REGISTERED),
        "guarded_documents": list(TEMPORAL_FAIL_CLOSED),
        "guarded_document_count": len(TEMPORAL_FAIL_CLOSED),
        "rule": (
            "retrievable_but_not_promotable_as_applicable_without_"
            "authoritative_temporal_evidence"
        ),
        "ui_requirement": (
            "show_temporal_status_unknown_and_do_not_state_current_"
            "applicability_for_guarded_document"
        ),
        "calculation_requirement": (
            "guarded_document_must_not_activate_temporal_rate_or_"
            "deterministic_rule_without_evidence"
        ),
        "human_acceptance_required": True,
        "automatically_accepted": False,
    }


def build_redistribution_matrix() -> list[dict[str, Any]]:
    return [
        {
            "document_id": document_id,
            "content_scope": "official_normative_text_only",
            "doctrine_or_editorial_content_in_public_runtime": False,
            "legal_basis_candidate": "LFDA_art_14_VIII",
            "official_text_conformity_required": True,
            "human_review_status": "pending",
            "automatic_redistribution_authorization": False,
        }
        for document_id in NORMATIVE_DOCUMENTS
    ]


def execute(
    *,
    preproduction_report_path: Path,
    model_license_evidence_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    preproduction = load_json(preproduction_report_path)
    validate_preproduction(preproduction)

    evidence = load_json(model_license_evidence_path)
    validate_model_license_evidence(evidence)

    temporal_policy = build_temporal_policy()
    redistribution = build_redistribution_matrix()

    decision = Decision(
        technical_preproduction_complete=True,
        model_license_metadata_verified=True,
        model_license_review_required=False,
        temporal_fail_closed_policy_ready=True,
        temporal_policy_human_acceptance_required=True,
        redistribution_human_review_required=True,
        publication_legal_acceptance=False,
        public_release_allowed=False,
        git_push_allowed=False,
        github_release_allowed=False,
        render_deploy_allowed=False,
        decision="DO_NOT_PUBLISH",
    )

    payload: dict[str, Any] = {
        "sprint": "19I.18Q",
        "canonical_sha256": EXPECTED_CANONICAL_SHA256,
        **asdict(decision),
        "model_license": {
            "model_id": EXPECTED_MODEL_ID,
            "license": EXPECTED_MODEL_LICENSE,
            "evidence": evidence,
        },
        "temporal_policy": temporal_policy,
        "redistribution_matrix": redistribution,
        "remaining_human_decisions": [
            "accept_or_reject_temporal_fail_closed_release_policy",
            "approve_or_reject_normative_text_redistribution_after_human_review",
        ],
        "automatic_publication_performed": False,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "publication_decision_dossier.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "human_decision_template.json").write_text(
        json.dumps(
            {
                "temporal_fail_closed_release_policy": "PENDING",
                "normative_text_redistribution": "PENDING",
                "reviewer": "",
                "review_date": "",
                "notes": "",
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return payload
