from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from app.services.runtime_official_source_audit import OfficialSourceAuditError


@dataclass(frozen=True)
class NormativeLegalGateDocument:
    document_id: str
    evidence_class: str | None
    content_conformant: bool
    runtime_to_local_pdf_verified: bool
    local_pdf_to_official_verified: bool
    redistribution_policy_verified: bool
    legal_basis_candidate_supported: bool
    disposition: str
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class NormativeLegalGateSummary:
    observed_documents: int
    legal_basis_candidate_documents: tuple[str, ...]
    official_provenance_pending_documents: tuple[str, ...]
    separate_review_documents: tuple[str, ...]
    redistribution_review_pending_documents: tuple[str, ...]
    automatic_promotion_performed: bool
    public_release_allowed: bool
    documents: tuple[NormativeLegalGateDocument, ...]


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OfficialSourceAuditError(f"No se pudo leer JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise OfficialSourceAuditError(f"{path} debe contener un objeto JSON.")
    return payload


def _index_documents(
    payload: dict[str, object],
    *,
    key: str = "documents",
) -> dict[str, dict[str, object]]:
    raw = payload.get(key)
    if not isinstance(raw, list):
        raise OfficialSourceAuditError(f"Campo {key} inválido.")
    result: dict[str, dict[str, object]] = {}
    for item in raw:
        if not isinstance(item, dict):
            raise OfficialSourceAuditError(f"Entrada inválida en {key}.")
        document_id = item.get("document_id")
        if not isinstance(document_id, str) or not document_id:
            raise OfficialSourceAuditError("document_id inválido.")
        if document_id in result:
            raise OfficialSourceAuditError(
                f"document_id duplicado: {document_id}"
            )
        result[document_id] = item
    return result


def evaluate_normative_legal_basis_gate(
    *,
    decision_matrix_path: Path,
    evidence_registry_path: Path,
    legal_basis_registry_path: Path,
) -> NormativeLegalGateSummary:
    matrix_payload = _read_json(decision_matrix_path)
    evidence_payload = _read_json(evidence_registry_path)
    legal_payload = _read_json(legal_basis_registry_path)

    matrix = _index_documents(matrix_payload)
    evidence = _index_documents(evidence_payload)

    decision_policy = legal_payload.get("decision_policy")
    sources = legal_payload.get("sources")
    if not isinstance(decision_policy, dict):
        raise OfficialSourceAuditError("decision_policy inválido.")
    if not isinstance(sources, list) or not sources:
        raise OfficialSourceAuditError("sources inválido.")

    required_source_ids = {"mx_lfda_art14_viii", "mx_dof_legal_notice"}
    source_ids = {
        item.get("id")
        for item in sources
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    if not required_source_ids.issubset(source_ids):
        raise OfficialSourceAuditError(
            "Falta evidencia jurídica normativa requerida."
        )

    if set(matrix) != set(evidence):
        raise OfficialSourceAuditError(
            "La matriz 19I.18J.3 y el registro 19I.18F deben cubrir "
            "exactamente los mismos documentos."
        )

    raw_separate = decision_policy.get("separate_review_documents")
    if not isinstance(raw_separate, list) or not all(
        isinstance(item, str) for item in raw_separate
    ):
        raise OfficialSourceAuditError("separate_review_documents inválido.")
    separate_policy = set(raw_separate)

    candidate_docs: list[str] = []
    provenance_pending: list[str] = []
    separate_docs: list[str] = []
    redistribution_pending: list[str] = []
    rows: list[NormativeLegalGateDocument] = []

    for document_id in sorted(matrix):
        matrix_item = matrix[document_id]
        evidence_item = evidence[document_id]

        evidence_class = evidence_item.get("evidence_class")
        if evidence_class is not None and not isinstance(evidence_class, str):
            raise OfficialSourceAuditError(
                f"evidence_class inválido para {document_id}."
            )

        content_conformant = matrix_item.get("content_conformant") is True
        bridge_verified = (
            matrix_item.get("runtime_to_local_pdf_verified") is True
        )
        official_verified = (
            matrix_item.get("local_pdf_to_official_verified") is True
        )
        redistribution_status = matrix_item.get(
            "publication_policy_status"
        )
        if not isinstance(redistribution_status, str):
            raise OfficialSourceAuditError(
                f"publication_policy_status inválido para {document_id}."
            )
        redistribution_verified = (
            redistribution_status == "public_redistribution_verified"
        )

        blockers: list[str] = []
        is_separate = document_id in separate_policy
        statutory_candidate = (
            evidence_class == "statutory_text_exclusion_candidate"
        )

        if is_separate:
            separate_docs.append(document_id)
            disposition = "separate_license_review_required"
            blockers.append("outside_statutory_text_gate")
        elif not statutory_candidate:
            disposition = "unsupported_legal_evidence_class"
            blockers.append("statutory_text_evidence_class_required")
        else:
            if not content_conformant:
                blockers.append("content_conformity_not_verified")
            if not bridge_verified:
                blockers.append("runtime_to_local_pdf_not_verified")
            if not official_verified:
                blockers.append("exact_official_provenance_not_verified")
                provenance_pending.append(document_id)

            legal_basis_supported = (
                content_conformant
                and bridge_verified
                and official_verified
            )
            if legal_basis_supported:
                candidate_docs.append(document_id)
                disposition = (
                    "legal_basis_candidate_supported_pending_"
                    "redistribution_review"
                )
            else:
                disposition = "legal_basis_candidate_blocked"

        if not redistribution_verified:
            redistribution_pending.append(document_id)
            blockers.append("redistribution_policy_not_verified")

        legal_basis_candidate_supported = (
            statutory_candidate
            and not is_separate
            and content_conformant
            and bridge_verified
            and official_verified
        )

        rows.append(
            NormativeLegalGateDocument(
                document_id=document_id,
                evidence_class=evidence_class,
                content_conformant=content_conformant,
                runtime_to_local_pdf_verified=bridge_verified,
                local_pdf_to_official_verified=official_verified,
                redistribution_policy_verified=redistribution_verified,
                legal_basis_candidate_supported=legal_basis_candidate_supported,
                disposition=disposition,
                blockers=tuple(dict.fromkeys(blockers)),
            )
        )

    return NormativeLegalGateSummary(
        observed_documents=len(matrix),
        legal_basis_candidate_documents=tuple(candidate_docs),
        official_provenance_pending_documents=tuple(
            sorted(set(provenance_pending))
        ),
        separate_review_documents=tuple(sorted(set(separate_docs))),
        redistribution_review_pending_documents=tuple(
            sorted(set(redistribution_pending))
        ),
        automatic_promotion_performed=False,
        public_release_allowed=False,
        documents=tuple(rows),
    )


def write_normative_legal_basis_gate_report(
    summary: NormativeLegalGateSummary,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(asdict(summary), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
