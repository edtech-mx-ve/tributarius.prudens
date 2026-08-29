from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


class RuntimePublicationEvidenceError(RuntimeError):
    """Fallo controlado al auditar evidencia de redistribución."""


@dataclass(frozen=True)
class PublicationEvidenceSummary:
    policy_documents: int
    evidence_documents: int
    statutory_candidates: int
    separate_license_review: int
    missing_evidence_documents: tuple[str, ...]
    extra_evidence_documents: tuple[str, ...]
    promotion_ready_documents: tuple[str, ...]


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimePublicationEvidenceError(
            f"No se pudo leer JSON: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimePublicationEvidenceError(f"{path} debe contener un objeto.")
    return payload


def _documents_by_id(
    payload: dict[str, object],
    *,
    source_name: str,
) -> dict[str, dict[str, object]]:
    raw_documents = payload.get("documents")
    if not isinstance(raw_documents, list):
        raise RuntimePublicationEvidenceError(
            f"{source_name}.documents debe ser una lista."
        )
    result: dict[str, dict[str, object]] = {}
    for raw in raw_documents:
        if not isinstance(raw, dict):
            raise RuntimePublicationEvidenceError(
                f"Entrada inválida en {source_name}.documents."
            )
        document_id = raw.get("document_id")
        if not isinstance(document_id, str) or not document_id.strip():
            raise RuntimePublicationEvidenceError(
                f"document_id inválido en {source_name}."
            )
        if document_id in result:
            raise RuntimePublicationEvidenceError(
                f"document_id duplicado en {source_name}: {document_id}"
            )
        result[document_id] = raw
    return result


def audit_publication_evidence(
    *,
    policy_path: Path,
    evidence_path: Path,
) -> PublicationEvidenceSummary:
    policy_payload = _read_json(policy_path)
    evidence_payload = _read_json(evidence_path)
    policy = _documents_by_id(policy_payload, source_name="policy")
    evidence = _documents_by_id(evidence_payload, source_name="evidence")

    missing = tuple(sorted(set(policy) - set(evidence)))
    extra = tuple(sorted(set(evidence) - set(policy)))

    statutory = 0
    separate = 0
    promotion_ready: list[str] = []

    legal_basis = evidence_payload.get("legal_basis")
    if not isinstance(legal_basis, dict):
        raise RuntimePublicationEvidenceError("legal_basis faltante.")
    if legal_basis.get("id") != "mx_lfda_art14_viii":
        raise RuntimePublicationEvidenceError("legal_basis.id inesperado.")
    official_url = legal_basis.get("official_url")
    if not isinstance(official_url, str) or not official_url.startswith("https://"):
        raise RuntimePublicationEvidenceError(
            "legal_basis.official_url debe ser HTTPS."
        )

    for document_id, raw in evidence.items():
        evidence_class = raw.get("evidence_class")
        policy_status = raw.get("publication_policy_status")
        if policy_status != "unknown_requires_review":
            raise RuntimePublicationEvidenceError(
                f"{document_id}: 19I.18F no puede promover estado de publicación."
            )
        if evidence_class == "statutory_text_exclusion_candidate":
            statutory += 1
            if raw.get("legal_basis_id") != "mx_lfda_art14_viii":
                raise RuntimePublicationEvidenceError(
                    f"{document_id}: base legal faltante."
                )
            if raw.get("content_conformity_required") is not True:
                raise RuntimePublicationEvidenceError(
                    f"{document_id}: debe exigir auditoría de conformidad."
                )
        elif evidence_class == "separate_license_review_required":
            separate += 1
        else:
            raise RuntimePublicationEvidenceError(
                f"{document_id}: evidence_class inválida."
            )

        policy_entry = policy.get(document_id)
        if policy_entry is not None and (
            policy_entry.get("redistribution_status")
            == "public_redistribution_verified"
        ):
            promotion_ready.append(document_id)

    return PublicationEvidenceSummary(
        policy_documents=len(policy),
        evidence_documents=len(evidence),
        statutory_candidates=statutory,
        separate_license_review=separate,
        missing_evidence_documents=missing,
        extra_evidence_documents=extra,
        promotion_ready_documents=tuple(sorted(promotion_ready)),
    )


def write_evidence_audit_report(
    summary: PublicationEvidenceSummary,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(asdict(summary), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
