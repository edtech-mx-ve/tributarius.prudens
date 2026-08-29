from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

CAMARA_DOCUMENTS = (
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
)
RMF_DOCUMENT = "rmf_2026"
SEPARATE_REVIEW_DOCUMENTS = ("manual_unam", "prodecon")
NORMATIVE_DOCUMENTS = CAMARA_DOCUMENTS + (RMF_DOCUMENT,)


class ProvenanceReconciliationError(RuntimeError):
    """Raised when provenance evidence cannot be reconciled safely."""


@dataclass(frozen=True)
class DocumentDecision:
    document_id: str
    category: str
    local_bridge_verified: bool
    technical_conformity_passed: bool
    official_provenance_status: str
    official_provenance_verified: bool
    legal_basis_status: str
    redistribution_status: str
    temporal_status: str
    blockers: tuple[str, ...]
    publication_ready: bool


def _load_json(path: Path, *, required: bool = True) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise ProvenanceReconciliationError(f"Falta artefacto requerido: {path}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProvenanceReconciliationError(
            f"No se pudo leer JSON válido: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise ProvenanceReconciliationError(
            f"Se esperaba objeto JSON en: {path}"
        )
    return payload


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for key in (
        "documents",
        "items",
        "entries",
        "results",
        "decisions",
        "evidence",
        "document_results",
    ):
        value = payload.get(key)
        if isinstance(value, list):
            candidates.extend(row for row in value if isinstance(row, dict))
    return candidates


def _doc_id(row: dict[str, Any]) -> str | None:
    for key in ("document_id", "id", "doc_id"):
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in _rows(payload):
        document_id = _doc_id(row)
        if document_id is not None:
            result[document_id] = row
    return result


def _string_set(payload: dict[str, Any], keys: Iterable[str]) -> set[str]:
    values: set[str] = set()
    for key in keys:
        raw = payload.get(key)
        if isinstance(raw, list):
            values.update(item for item in raw if isinstance(item, str))
    return values


def _bool(row: dict[str, Any] | None, keys: Iterable[str]) -> bool:
    if row is None:
        return False
    for key in keys:
        value = row.get(key)
        if isinstance(value, bool):
            return value
    return False


def _str(row: dict[str, Any] | None, keys: Iterable[str]) -> str | None:
    if row is None:
        return None
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _browser_exact_documents(payload: dict[str, Any]) -> set[str]:
    exact = _string_set(
        payload,
        (
            "exact_binary_verified_documents",
            "exact_binary_official_source_verified_documents",
            "verified_documents",
        ),
    )
    for document_id, row in _index(payload).items():
        status = _str(
            row,
            (
                "status",
                "official_provenance_status",
                "comparison_status",
            ),
        )
        exact_match = _bool(
            row,
            (
                "exact_binary_match",
                "official_provenance_verified",
                "verified",
            ),
        )
        if status == "exact_binary_official_source_verified" or exact_match:
            exact.add(document_id)
    return exact


def _rmf_exact(payload: dict[str, Any]) -> bool:
    exact = _string_set(
        payload,
        (
            "official_provenance_verified_documents",
            "exact_binary_verified_documents",
        ),
    )
    if RMF_DOCUMENT in exact:
        return True
    row = _index(payload).get(RMF_DOCUMENT)
    status = _str(row, ("status", "official_provenance_status"))
    return bool(
        status == "exact_binary_official_source_verified"
        or _bool(row, ("official_provenance_verified", "exact_binary_match"))
    )


def _redistribution_status(
    document_id: str,
    policy_index: dict[str, dict[str, Any]],
) -> str:
    row = policy_index.get(document_id)
    value = _str(
        row,
        (
            "publication_policy_status",
            "redistribution_status",
            "status",
        ),
    )
    if value in {
        "public_redistribution_verified",
        "restricted_or_internal_only",
        "unknown_requires_review",
    }:
        return value
    return "unknown_requires_review"


def _legal_basis_status(
    document_id: str,
    legal_index: dict[str, dict[str, Any]],
) -> str:
    row = legal_index.get(document_id)
    return (
        _str(
            row,
            (
                "disposition",
                "legal_basis_status",
                "status",
            ),
        )
        or "not_established"
    )


def _temporal_status(
    document_id: str,
    temporal_index: dict[str, dict[str, Any]],
) -> str:
    row = temporal_index.get(document_id)
    if row is None:
        return "unknown_fail_closed"
    if _bool(row, ("document_wide_validity_verified", "temporal_verified")):
        return "verified"
    value = _str(
        row,
        (
            "status",
            "temporal_status",
            "document_wide_status",
        ),
    )
    return value or "unknown_fail_closed"


def reconcile_official_provenance(
    *,
    browser_bridge_path: Path,
    online_provenance_path: Path,
    local_bridge_path: Path,
    conformity_path: Path,
    legal_basis_path: Path,
    publication_policy_path: Path,
    temporal_registry_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    browser = _load_json(browser_bridge_path)
    online = _load_json(online_provenance_path)
    local_bridge = _load_json(local_bridge_path)
    conformity = _load_json(conformity_path)
    legal_basis = _load_json(legal_basis_path)
    publication_policy = _load_json(publication_policy_path)
    temporal_registry = _load_json(temporal_registry_path)

    browser_exact = _browser_exact_documents(browser)
    local_index = _index(local_bridge)
    conformity_index = _index(conformity)
    legal_index = _index(legal_basis)
    policy_index = _index(publication_policy)
    temporal_index = _index(temporal_registry)

    decisions: list[DocumentDecision] = []

    for document_id in NORMATIVE_DOCUMENTS:
        local_ok = _bool(
            local_index.get(document_id),
            ("bridge_verified", "local_bridge_verified", "verified"),
        )
        conformity_ok = _bool(
            conformity_index.get(document_id),
            ("technical_conformity_passed", "technically_conformant"),
        )

        if document_id in CAMARA_DOCUMENTS:
            provenance_ok = document_id in browser_exact
            provenance_status = (
                "exact_binary_official_source_verified"
                if provenance_ok
                else "official_provenance_not_verified"
            )
        else:
            provenance_ok = _rmf_exact(online)
            provenance_status = (
                "exact_binary_official_source_verified"
                if provenance_ok
                else "official_provenance_not_verified"
            )

        legal_status = _legal_basis_status(document_id, legal_index)
        redistribution = _redistribution_status(document_id, policy_index)
        temporal = _temporal_status(document_id, temporal_index)

        blockers: list[str] = []
        if not local_ok:
            blockers.append("local_runtime_to_source_bridge_not_verified")
        if not conformity_ok:
            blockers.append("technical_conformity_not_verified")
        if not provenance_ok:
            blockers.append("official_binary_provenance_not_verified")
        if redistribution != "public_redistribution_verified":
            blockers.append("public_redistribution_not_verified")
        if temporal != "verified":
            blockers.append("document_wide_temporal_validity_not_verified")

        publication_ready = not blockers
        decisions.append(
            DocumentDecision(
                document_id=document_id,
                category="normative",
                local_bridge_verified=local_ok,
                technical_conformity_passed=conformity_ok,
                official_provenance_status=provenance_status,
                official_provenance_verified=provenance_ok,
                legal_basis_status=legal_status,
                redistribution_status=redistribution,
                temporal_status=temporal,
                blockers=tuple(blockers),
                publication_ready=publication_ready,
            )
        )

    for document_id in SEPARATE_REVIEW_DOCUMENTS:
        redistribution = _redistribution_status(document_id, policy_index)
        decisions.append(
            DocumentDecision(
                document_id=document_id,
                category="doctrine_or_orientation_separate_review",
                local_bridge_verified=_bool(
                    local_index.get(document_id),
                    ("bridge_verified", "local_bridge_verified", "verified"),
                ),
                technical_conformity_passed=_bool(
                    conformity_index.get(document_id),
                    ("technical_conformity_passed", "technically_conformant"),
                ),
                official_provenance_status="not_applicable_as_normative_source",
                official_provenance_verified=False,
                legal_basis_status="separate_license_review_required",
                redistribution_status=redistribution,
                temporal_status="not_applicable",
                blockers=("separate_license_review_required",),
                publication_ready=False,
            )
        )

    exact_normative = [
        row.document_id
        for row in decisions
        if row.category == "normative" and row.official_provenance_verified
    ]
    normative_publication_ready = [
        row.document_id
        for row in decisions
        if row.category == "normative" and row.publication_ready
    ]
    blocked = [row.document_id for row in decisions if not row.publication_ready]

    report = {
        "sprint": "19I.18J.10",
        "decision_mode": "fail_closed",
        "observed_documents": len(decisions),
        "normative_documents": list(NORMATIVE_DOCUMENTS),
        "official_provenance_exact_normative_documents": exact_normative,
        "official_provenance_exact_normative_count": len(exact_normative),
        "normative_publication_ready_documents": normative_publication_ready,
        "separate_license_review_documents": list(SEPARATE_REVIEW_DOCUMENTS),
        "blocked_documents": blocked,
        "documents": [asdict(row) for row in decisions],
        "official_provenance_complete_for_normative_corpus": (
            len(exact_normative) == len(NORMATIVE_DOCUMENTS)
        ),
        "public_release_allowed": not blocked,
        "git_push_allowed": False,
        "github_release_allowed": False,
        "render_deploy_allowed": False,
        "automatic_promotion_performed": False,
        "notes": [
            (
                "La procedencia binaria oficial, la redistribución y la "
                "vigencia temporal son controles independientes."
            ),
            (
                "La verificación de procedencia no concede derechos de "
                "redistribución ni determina vigencia jurídica."
            ),
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report
