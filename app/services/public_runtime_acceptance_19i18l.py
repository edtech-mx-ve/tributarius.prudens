from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

PUBLIC_SHA = "7b4bb564cdfbd849a961790bcfad938d09369ffc41edc2de4cedce1cab2c49b0"
PARENTS = 2962
DOCS = {
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
}
DIRECT = {
    "cff",
    "cpeum",
    "lfisan",
    "lfpca",
    "lieps",
    "lif_2026",
    "lisr",
    "liva",
    "lotfja",
    "reg_cff",
    "reg_lisr_060516",
}
REBUILT = {"lfdc", "reg_liva_250914"}
DOF = {"rmf_2026"}
TEMPORAL = {"lif_2026", "rmf_2026"}


class AcceptanceError(RuntimeError):
    """Fail-closed acceptance error for Sprint 19I.18L."""


@dataclass(frozen=True)
class Decision:
    document_id: str
    provenance_status: str
    provenance_chain: str
    redistribution_status: str
    temporal_status: str
    runtime_policy: str


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AcceptanceError(f"JSON inválido: {path}") from exc
    if not isinstance(value, dict):
        raise AcceptanceError(f"Objeto JSON esperado: {path}")
    return value


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def decisions() -> list[Decision]:
    result: list[Decision] = []
    for document_id in sorted(DOCS):
        if document_id in DIRECT:
            provenance_status = "official_exact_binary_verified"
            provenance_chain = "browser_official_evidence->J7_exact->J10"
        elif document_id in REBUILT:
            provenance_status = "official_rebuild_chain_verified"
            provenance_chain = (
                "browser_official_evidence->J12.1->J12.2->J12.3->J12.4->K"
            )
        elif document_id in DOF:
            provenance_status = "official_exact_binary_verified"
            provenance_chain = "dof_official_evidence->J_exact->J10"
        else:
            raise AcceptanceError(f"Sin procedencia: {document_id}")

        if document_id in TEMPORAL:
            temporal_status = "temporal_evidence_registered"
            runtime_policy = "eligible_subject_to_query_date_and_normative_rules"
        else:
            temporal_status = "temporal_evidence_incomplete_fail_closed"
            runtime_policy = (
                "retrievable_but_not_promotable_as_applicable_without_evidence"
            )

        result.append(
            Decision(
                document_id=document_id,
                provenance_status=provenance_status,
                provenance_chain=provenance_chain,
                redistribution_status=(
                    "statutory_text_exclusion_candidate_human_review_required"
                ),
                temporal_status=temporal_status,
                runtime_policy=runtime_policy,
            )
        )
    return result


def execute(runtime_dir: Path, output: Path) -> dict[str, Any]:
    report = _load(runtime_dir / "public_safe_runtime_acceptance.json")
    candidates = sorted((runtime_dir / "canonical").glob("*.jsonl"))
    if len(candidates) != 1:
        raise AcceptanceError("Canonical público ambiguo/ausente")

    if (
        _sha(candidates[0]) != PUBLIC_SHA
        or report.get("canonical_sha256") != PUBLIC_SHA
    ):
        raise AcceptanceError("SHA público no aprobado")

    if (
        report.get("parent_count") != PARENTS
        or report.get("normative_document_count") != 14
    ):
        raise AcceptanceError("Composición 19K inválida")

    if (
        report.get("benchmark_passed") is not True
        or report.get("blocked_content_absent") is not True
        or report.get("technical_local_acceptance") is not True
    ):
        raise AcceptanceError("Aceptación técnica 19K incompleta")

    items = decisions()
    provenance_complete = (
        {item.document_id for item in items} == DOCS
        and all(
            item.provenance_status.startswith("official_")
            for item in items
        )
    )
    redistribution_complete = all(
        item.redistribution_status == "redistribution_human_approved"
        for item in items
    )
    temporal_complete = all(
        item.temporal_status == "temporal_evidence_registered"
        for item in items
    )
    temporal_fail_closed = all(
        item.document_id in TEMPORAL
        or item.runtime_policy
        == "retrievable_but_not_promotable_as_applicable_without_evidence"
        for item in items
    )
    allowed = (
        provenance_complete
        and redistribution_complete
        and temporal_complete
        and temporal_fail_closed
    )

    result: dict[str, Any] = {
        "sprint": "19I.18L",
        "status": "legal_provenance_temporal_local_acceptance",
        "public_runtime_sha256": PUBLIC_SHA,
        "public_runtime_parent_count": PARENTS,
        "normative_document_count": 14,
        "provenance_complete": provenance_complete,
        "direct_official_exact_documents": sorted(DIRECT | DOF),
        "official_rebuild_chain_documents": sorted(REBUILT),
        "redistribution_human_review_required": not redistribution_complete,
        "redistribution_complete": redistribution_complete,
        "legal_basis_status": (
            "statutory_text_exclusion_candidate_with_human_review_required"
        ),
        "temporal_evidence_registered_documents": sorted(TEMPORAL),
        "temporal_guarded_documents": sorted(DOCS - TEMPORAL),
        "temporal_validity_complete": temporal_complete,
        "temporal_fail_closed_complete": temporal_fail_closed,
        "technical_local_acceptance": True,
        "legal_local_acceptance": provenance_complete and temporal_fail_closed,
        "publication_legal_acceptance": redistribution_complete,
        "automatic_legal_promotion_performed": False,
        "automatic_temporal_promotion_performed": False,
        "public_release_allowed": allowed,
        "git_push_allowed": allowed,
        "github_release_allowed": allowed,
        "render_deploy_allowed": allowed,
        "documents": [asdict(item) for item in items],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result
