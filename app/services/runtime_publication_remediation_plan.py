from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from app.services.runtime_official_source_audit import OfficialSourceAuditError


@dataclass(frozen=True)
class RemediationTrack:
    track_id: str
    documents: tuple[str, ...]
    blocker: str
    required_action: str
    automation_allowed: bool
    publication_effect: str


@dataclass(frozen=True)
class PublicationRemediationPlan:
    observed_documents: int
    ready_documents: tuple[str, ...]
    blocked_documents: tuple[str, ...]
    tracks: tuple[RemediationTrack, ...]
    next_safe_action: str
    git_push_allowed: bool
    github_release_allowed: bool
    render_deploy_allowed: bool
    public_release_allowed: bool


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OfficialSourceAuditError(f"No se pudo leer JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise OfficialSourceAuditError(f"{path} debe contener un objeto JSON.")
    return payload


def _require_string_list(
    payload: dict[str, object],
    key: str,
) -> tuple[str, ...]:
    raw = payload.get(key)
    if not isinstance(raw, list) or not all(
        isinstance(item, str) and item for item in raw
    ):
        raise OfficialSourceAuditError(f"Campo {key} inválido.")
    if len(set(raw)) != len(raw):
        raise OfficialSourceAuditError(f"Campo {key} contiene duplicados.")
    return tuple(raw)


def build_publication_remediation_plan(
    *,
    decision_matrix_path: Path,
    legal_gate_path: Path,
) -> PublicationRemediationPlan:
    matrix = _read_json(decision_matrix_path)
    gate = _read_json(legal_gate_path)

    ready = _require_string_list(matrix, "publication_ready_documents")
    blocked = _require_string_list(matrix, "blocked_documents")
    provenance_pending = _require_string_list(
        gate,
        "official_provenance_pending_documents",
    )
    separate_review = _require_string_list(gate, "separate_review_documents")
    legal_candidates = _require_string_list(
        gate,
        "legal_basis_candidate_documents",
    )
    redistribution_pending = set(
        _require_string_list(
            gate,
            "redistribution_review_pending_documents",
        )
    )

    observed = matrix.get("observed_documents")
    if not isinstance(observed, int) or observed <= 0:
        raise OfficialSourceAuditError("observed_documents inválido.")
    if observed != len(ready) + len(blocked):
        raise OfficialSourceAuditError(
            "Cobertura inconsistente entre ready y blocked."
        )
    if set(ready) & set(blocked):
        raise OfficialSourceAuditError(
            "Un documento no puede estar simultáneamente ready y blocked."
        )

    known = set(ready) | set(blocked)
    for label, docs in (
        ("official_provenance_pending_documents", provenance_pending),
        ("separate_review_documents", separate_review),
        ("legal_basis_candidate_documents", legal_candidates),
    ):
        if not set(docs).issubset(known):
            raise OfficialSourceAuditError(
                f"{label} contiene documentos fuera de la matriz."
            )

    candidate_review = tuple(
        sorted(set(legal_candidates) & redistribution_pending)
    )
    remaining_redistribution = tuple(
        sorted(
            redistribution_pending
            - set(provenance_pending)
            - set(separate_review)
            - set(candidate_review)
        )
    )

    tracks: list[RemediationTrack] = []

    if provenance_pending:
        tracks.append(
            RemediationTrack(
                track_id="A_official_provenance",
                documents=tuple(sorted(provenance_pending)),
                blocker="exact_official_provenance_not_verified",
                required_action=(
                    "Adquirir evidencia oficial desde una red/máquina con "
                    "acceso y verificar offline con 19I.18J.2."
                ),
                automation_allowed=True,
                publication_effect=(
                    "Solo elimina el bloqueo de procedencia; no verifica "
                    "redistribución."
                ),
            )
        )

    if candidate_review:
        tracks.append(
            RemediationTrack(
                track_id="B_normative_redistribution_review",
                documents=candidate_review,
                blocker="redistribution_policy_not_verified",
                required_action=(
                    "Registrar una decisión explícita de redistribución "
                    "basada en evidencia jurídica y contexto de uso; no "
                    "inferir permiso automáticamente."
                ),
                automation_allowed=False,
                publication_effect=(
                    "Puede habilitar el gate normativo solo tras revisión "
                    "explícita y documentada."
                ),
            )
        )

    if separate_review:
        tracks.append(
            RemediationTrack(
                track_id="C_separate_license_review",
                documents=tuple(sorted(separate_review)),
                blocker="separate_license_review_required",
                required_action=(
                    "Obtener autorización/licencia explícita o excluir estos "
                    "documentos del runtime público."
                ),
                automation_allowed=False,
                publication_effect=(
                    "No existe promoción automática desde el gate de textos "
                    "normativos."
                ),
            )
        )

    if remaining_redistribution:
        tracks.append(
            RemediationTrack(
                track_id="D_other_redistribution_review",
                documents=remaining_redistribution,
                blocker="redistribution_policy_not_verified",
                required_action=(
                    "Resolver la política de redistribución después de cerrar "
                    "los gates técnicos previos."
                ),
                automation_allowed=False,
                publication_effect=(
                    "Mantiene fail-closed hasta decisión explícita."
                ),
            )
        )

    public_release_allowed = matrix.get("public_release_allowed") is True
    if public_release_allowed:
        next_action = "final_publication_validation"
    elif provenance_pending:
        next_action = "acquire_official_evidence_19i18j2"
    elif candidate_review:
        next_action = "explicit_normative_redistribution_review"
    elif separate_review:
        next_action = "exclude_or_license_separate_review_documents"
    else:
        next_action = "resolve_remaining_publication_blockers"

    return PublicationRemediationPlan(
        observed_documents=observed,
        ready_documents=tuple(sorted(ready)),
        blocked_documents=tuple(sorted(blocked)),
        tracks=tuple(tracks),
        next_safe_action=next_action,
        git_push_allowed=False,
        github_release_allowed=False,
        render_deploy_allowed=False,
        public_release_allowed=public_release_allowed,
    )


def write_publication_remediation_plan(
    plan: PublicationRemediationPlan,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(asdict(plan), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
