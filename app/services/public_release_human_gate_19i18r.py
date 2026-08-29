from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

ALLOWED_DECISION = "APPROVED"
EXPECTED_PREVIOUS_DECISION = "DO_NOT_PUBLISH"
EXPECTED_NORMATIVE_DOCUMENT_COUNT = 14


class HumanReleaseDecisionError(RuntimeError):
    """Fail-closed validation error for the human release decision."""


@dataclass(frozen=True)
class ReleaseGate:
    human_decision_record_complete: bool
    temporal_fail_closed_release_policy_accepted: bool
    normative_text_redistribution_approved: bool
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
        raise HumanReleaseDecisionError(f"No se pudo leer JSON: {path}") from exc
    if not isinstance(value, dict):
        raise HumanReleaseDecisionError(f"Objeto JSON esperado: {path}")
    return value


def validate_dossier(dossier: dict[str, Any]) -> None:
    required = {
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
        "decision": EXPECTED_PREVIOUS_DECISION,
    }
    mismatches = {
        key: {"actual": dossier.get(key), "expected": expected}
        for key, expected in required.items()
        if dossier.get(key) != expected
    }
    matrix = dossier.get("redistribution_matrix")
    if not isinstance(matrix, list) or len(matrix) != EXPECTED_NORMATIVE_DOCUMENT_COUNT:
        mismatches["redistribution_matrix"] = {
            "actual": len(matrix) if isinstance(matrix, list) else None,
            "expected": EXPECTED_NORMATIVE_DOCUMENT_COUNT,
        }
    if mismatches:
        raise HumanReleaseDecisionError(f"Expediente 19Q inconsistente: {mismatches}")


def validate_human_decision(decision: dict[str, Any]) -> None:
    required = {
        "temporal_fail_closed_release_policy": ALLOWED_DECISION,
        "normative_text_redistribution": ALLOWED_DECISION,
        "scope": "public_normative_runtime_only",
        "doctrine_editorial_content_included": False,
        "acknowledges_temporal_fail_closed_constraints": True,
        "acknowledges_official_text_conformity_requirement": True,
    }
    mismatches = {
        key: {"actual": decision.get(key), "expected": expected}
        for key, expected in required.items()
        if decision.get(key) != expected
    }

    reviewer = decision.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip():
        mismatches["reviewer"] = {"actual": reviewer, "expected": "non-empty"}

    review_date = decision.get("review_date")
    try:
        parsed_date = date.fromisoformat(str(review_date))
    except ValueError:
        parsed_date = None
    if parsed_date is None:
        mismatches["review_date"] = {
            "actual": review_date,
            "expected": "YYYY-MM-DD",
        }

    statement = decision.get("decision_statement")
    if not isinstance(statement, str) or "Acepto ambas decisiones" not in statement:
        mismatches["decision_statement"] = {
            "actual": statement,
            "expected": "explicit acceptance statement",
        }

    if mismatches:
        raise HumanReleaseDecisionError(f"Decisión humana inválida: {mismatches}")


def execute(
    *,
    dossier_path: Path,
    human_decision_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    dossier = load_json(dossier_path)
    decision = load_json(human_decision_path)
    validate_dossier(dossier)
    validate_human_decision(decision)

    gate = ReleaseGate(
        human_decision_record_complete=True,
        temporal_fail_closed_release_policy_accepted=True,
        normative_text_redistribution_approved=True,
        publication_legal_acceptance=True,
        public_release_allowed=True,
        git_push_allowed=True,
        github_release_allowed=True,
        render_deploy_allowed=True,
        decision="APPROVED_FOR_CONTROLLED_PUBLICATION",
    )
    payload: dict[str, Any] = {
        "sprint": "19I.18R",
        **asdict(gate),
        "scope": "public_normative_runtime_only",
        "doctrine_editorial_content_included": False,
        "temporal_policy": dossier["temporal_policy"],
        "human_decision": decision,
        "conditions": [
            "publish_only_the_audited_normative_runtime_candidate",
            "preserve_temporal_fail_closed_behavior",
            "do_not_add_doctrine_or_editorial_content",
            "preserve_official_text_conformity_and_provenance",
            "run_post_deploy_smoke_before_declaring_production_acceptance",
        ],
        "automatic_deployment_performed": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload
