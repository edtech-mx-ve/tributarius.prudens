from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from app.services.runtime_official_source_audit import OfficialSourceAuditError


@dataclass(frozen=True)
class PublicationDecisionDocument:
    document_id: str
    runtime_chunks: int
    publication_policy_status: str
    legal_evidence_class: str | None
    content_conformant: bool
    runtime_to_local_pdf_verified: bool
    local_pdf_to_official_verified: bool
    official_source_status: str
    blockers: tuple[str, ...]
    publication_ready: bool


@dataclass(frozen=True)
class PublicationDecisionSummary:
    observed_documents: int
    publication_ready_documents: tuple[str, ...]
    blocked_documents: tuple[str, ...]
    unresolved_external_evidence_documents: tuple[str, ...]
    separate_license_review_documents: tuple[str, ...]
    public_release_allowed: bool
    documents: tuple[PublicationDecisionDocument, ...]


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OfficialSourceAuditError(f"No se pudo leer JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise OfficialSourceAuditError(f"{path} debe contener objeto JSON.")
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


def build_publication_decision_matrix(
    *,
    safety_report_path: Path,
    evidence_registry_path: Path,
    content_report_path: Path,
    source_bridge_report_path: Path,
    official_source_report_path: Path,
) -> PublicationDecisionSummary:
    safety = _index_documents(
        _read_json(safety_report_path),
        key="results",
    )
    evidence = _index_documents(
        _read_json(evidence_registry_path),
        key="documents",
    )
    content = _index_documents(_read_json(content_report_path))
    bridge = _index_documents(_read_json(source_bridge_report_path))
    official = _index_documents(_read_json(official_source_report_path))

    all_ids = set(safety)
    if set(evidence) != all_ids:
        raise OfficialSourceAuditError(
            "El registro 19I.18F no cubre exactamente los documentos 19I.18E."
        )

    normative_ids = set(content)
    if set(bridge) != normative_ids or set(official) != normative_ids:
        raise OfficialSourceAuditError(
            "19I.18G/19I.18I/19I.18J no cubren el mismo conjunto normativo."
        )
    if not normative_ids.issubset(all_ids):
        raise OfficialSourceAuditError(
            "Los documentos normativos no son subconjunto de safety."
        )

    ready: list[str] = []
    blocked: list[str] = []
    unresolved_external: list[str] = []
    separate_license: list[str] = []
    rows: list[PublicationDecisionDocument] = []

    for document_id in sorted(all_ids):
        safety_item = safety[document_id]
        evidence_item = evidence[document_id]

        chunks = safety_item.get("chunk_count")
        policy_status = safety_item.get("redistribution_status")
        evidence_class = evidence_item.get("evidence_class")
        if not isinstance(chunks, int) or chunks < 0:
            raise OfficialSourceAuditError(
                f"chunks inválido para {document_id}."
            )
        if not isinstance(policy_status, str):
            raise OfficialSourceAuditError(
                f"status inválido para {document_id}."
            )
        if evidence_class is not None and not isinstance(evidence_class, str):
            raise OfficialSourceAuditError(
                f"evidence_class inválido para {document_id}."
            )

        blockers: list[str] = []
        content_conformant = False
        bridge_verified = False
        official_verified = False
        official_status = "not_applicable_separate_license_review"

        if document_id in normative_ids:
            content_item = content[document_id]
            bridge_item = bridge[document_id]
            official_item = official[document_id]

            content_conformant = (
                content_item.get("technical_conformity_passed") is True
            )
            bridge_verified = bridge_item.get("bridge_verified") is True
            official_verified = (
                official_item.get("official_provenance_verified") is True
            )

            if official_verified:
                official_status = "exact_binary_official_source_verified"
            else:
                remote_hashes = official_item.get("remote_sha256_values")
                errors = official_item.get("fetch_errors")
                if (
                    isinstance(remote_hashes, list)
                    and remote_hashes
                ):
                    official_status = "official_binary_differs_or_unmatched"
                    blockers.append("official_binary_not_exact_local_match")
                elif isinstance(errors, list) and errors:
                    official_status = "official_source_unreachable_from_local_network"
                    blockers.append("external_official_source_evidence_pending")
                    unresolved_external.append(document_id)
                else:
                    official_status = "official_source_evidence_missing"
                    blockers.append("external_official_source_evidence_pending")
                    unresolved_external.append(document_id)

            if not content_conformant:
                blockers.append("content_conformity_not_verified")
            if not bridge_verified:
                blockers.append("runtime_to_local_pdf_not_verified")
            if not official_verified:
                blockers.append("local_pdf_to_official_not_verified")
        else:
            separate_license.append(document_id)
            blockers.append("separate_license_review_required")

        if policy_status != "public_redistribution_verified":
            blockers.append("redistribution_policy_not_verified")

        publication_ready = not blockers
        if publication_ready:
            ready.append(document_id)
        else:
            blocked.append(document_id)

        rows.append(
            PublicationDecisionDocument(
                document_id=document_id,
                runtime_chunks=chunks,
                publication_policy_status=policy_status,
                legal_evidence_class=evidence_class,
                content_conformant=content_conformant,
                runtime_to_local_pdf_verified=bridge_verified,
                local_pdf_to_official_verified=official_verified,
                official_source_status=official_status,
                blockers=tuple(dict.fromkeys(blockers)),
                publication_ready=publication_ready,
            )
        )

    return PublicationDecisionSummary(
        observed_documents=len(all_ids),
        publication_ready_documents=tuple(ready),
        blocked_documents=tuple(blocked),
        unresolved_external_evidence_documents=tuple(
            sorted(set(unresolved_external))
        ),
        separate_license_review_documents=tuple(sorted(separate_license)),
        public_release_allowed=bool(ready) and len(ready) == len(all_ids),
        documents=tuple(rows),
    )


def write_publication_decision_matrix(
    summary: PublicationDecisionSummary,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(asdict(summary), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
