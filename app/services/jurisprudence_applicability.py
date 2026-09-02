from __future__ import annotations

import re
import unicodedata

from app.domain.jurisprudence import JurisprudenceStatus, NormRelationType
from app.domain.jurisprudence_applicability import (
    SessionJurisprudenceApplicabilityAssessment,
)
from app.domain.jurisprudence_document import JurisprudenceDocumentRepresentation
from app.domain.jurisprudence_extraction import JurisprudenceExtractedMetadata
from app.domain.jurisprudence_session_retrieval import SessionJurisprudenceHit

_SPACE_RE = re.compile(r"\s+")


class JurisprudenceApplicabilityError(ValueError):
    pass


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_marks = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return _SPACE_RE.sub(" ", without_marks).strip()


def _shared_refs(
    extracted_refs: list[str],
    applicable_normative_refs: set[str],
) -> list[str]:
    normalized_applicable = {
        _normalize(reference): reference for reference in applicable_normative_refs
    }
    shared: list[str] = []
    for reference in extracted_refs:
        if _normalize(reference) in normalized_applicable:
            shared.append(reference)
    return shared


def assess_session_jurisprudence_applicability(
    *,
    hit: SessionJurisprudenceHit,
    document: JurisprudenceDocumentRepresentation,
    metadata: JurisprudenceExtractedMetadata,
    applicable_normative_refs: set[str],
    matter: str | None = None,
) -> SessionJurisprudenceApplicabilityAssessment:
    """Evalúa si un resultado temporal merece consideración en el problema jurídico.

    No convierte metadatos extraídos en metadatos verificados ni declara que el
    criterio resuelva el caso. Ese salto sería jurídicamente cómodo y técnicamente
    bastante temerario.
    """

    if hit.document_id != document.document_id:
        raise JurisprudenceApplicabilityError(
            "El hit no corresponde al documento jurisprudencial suministrado."
        )
    if hit.source_sha256 != document.source_sha256:
        raise JurisprudenceApplicabilityError(
            "La huella del hit no coincide con la del documento jurisprudencial."
        )
    if hit.page_number > document.page_count:
        raise JurisprudenceApplicabilityError(
            "La página recuperada no existe en el documento jurisprudencial."
        )

    reasons: list[str] = []
    requires_review = True
    relevant_to_problem = True

    shared_refs = _shared_refs(
        metadata.related_normative_refs,
        applicable_normative_refs,
    )
    relevant_to_norm = bool(shared_refs)

    if metadata.status in {
        JurisprudenceStatus.SUPERSEDED,
        JurisprudenceStatus.INVALIDATED,
    }:
        reasons.append(f"status_{metadata.status.value}")
        return SessionJurisprudenceApplicabilityAssessment(
            document_id=hit.document_id,
            page_number=hit.page_number,
            applicable_candidate=False,
            relevant_to_problem=False,
            relevant_to_norm=relevant_to_norm,
            shared_normative_refs=shared_refs,
            criterion_status=metadata.status,
            relation_type=metadata.relation_type,
            requires_human_review=True,
            reasons=reasons,
        )

    if metadata.status in {
        JurisprudenceStatus.UNKNOWN,
        JurisprudenceStatus.HISTORICAL,
    }:
        reasons.append(f"status_{metadata.status.value}")

    if matter is not None and metadata.matter is not None:
        if _normalize(metadata.matter) != _normalize(matter):
            reasons.append("matter_mismatch")
            relevant_to_problem = False

    if metadata.related_normative_refs:
        if not applicable_normative_refs:
            reasons.append("normative_context_missing")
            relevant_to_problem = False
        elif not shared_refs:
            reasons.append("no_shared_normative_ref")
            relevant_to_problem = False
    else:
        reasons.append("no_explicit_normative_ref")

    if metadata.relation_type is NormRelationType.CONFLICTS:
        reasons.append("relation_conflicts")
    elif metadata.relation_type is NormRelationType.UNKNOWN:
        reasons.append("relation_unknown")

    if metadata.identifier is None:
        reasons.append("identifier_missing")
    if metadata.title is None:
        reasons.append("title_missing")
    if metadata.court_or_body is None:
        reasons.append("court_or_body_missing")

    applicable_candidate = relevant_to_problem
    if not reasons:
        reasons.append("candidate_relevant_pending_verification")

    return SessionJurisprudenceApplicabilityAssessment(
        document_id=hit.document_id,
        page_number=hit.page_number,
        applicable_candidate=applicable_candidate,
        relevant_to_problem=relevant_to_problem,
        relevant_to_norm=relevant_to_norm,
        shared_normative_refs=shared_refs,
        criterion_status=metadata.status,
        relation_type=metadata.relation_type,
        requires_human_review=requires_review,
        reasons=reasons,
    )
