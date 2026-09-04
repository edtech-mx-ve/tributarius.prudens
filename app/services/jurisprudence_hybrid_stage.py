from __future__ import annotations

from datetime import date

from app.domain.jurisprudence_document import JurisprudenceDocumentRepresentation
from app.domain.jurisprudence_extraction import JurisprudenceExtractedMetadata
from app.domain.jurisprudence_hybrid import SessionJurisprudenceHybridResult
from app.domain.jurisprudence_normative_relations import (
    JurisprudenceNormativeRelationRecord,
)
from app.domain.jurisprudence_ratio import JurisprudenceRatioRecord
from app.domain.jurisprudence_temporal import JurisprudenceTemporalRecord
from app.services.jurisprudence_applicability import (
    assess_session_jurisprudence_applicability,
)
from app.services.jurisprudence_evidence_integration import (
    integrate_session_jurisprudence_evidence,
)
from app.services.jurisprudence_relations import analyze_jurisprudence_relations
from jurisprudence.retrieval import SessionJurisprudenceRetriever


def run_session_jurisprudence_stage(
    *,
    query: str,
    documents: list[JurisprudenceDocumentRepresentation],
    metadata_by_document_id: dict[str, JurisprudenceExtractedMetadata],
    applicable_normative_refs: set[str],
    matter: str | None,
    top_k: int,
    normative_relation_records: dict[
        str, JurisprudenceNormativeRelationRecord
    ] | None = None,
    temporal_records: dict[str, JurisprudenceTemporalRecord] | None = None,
    ratio_records: dict[str, JurisprudenceRatioRecord] | None = None,
    query_date: date | None = None,
) -> SessionJurisprudenceHybridResult:
    """Recupera y, cuando E.3/E.4 están disponibles, aplica la compuerta E.5."""

    documents_by_id = {document.document_id: document for document in documents}
    retrieval = SessionJurisprudenceRetriever(documents).search(query, top_k=top_k)

    applicability = []
    for hit in retrieval.hits:
        document = documents_by_id.get(hit.document_id)
        metadata = metadata_by_document_id.get(hit.document_id)
        if document is None or metadata is None:
            continue
        applicability.append(
            assess_session_jurisprudence_applicability(
                hit=hit,
                document=document,
                metadata=metadata,
                applicable_normative_refs=applicable_normative_refs,
                matter=matter,
            )
        )

    relations = analyze_jurisprudence_relations(applicability)
    evidence_integration = None

    if (
        normative_relation_records is not None
        and temporal_records is not None
        and ratio_records is not None
        and query_date is not None
    ):
        evidence_integration = integrate_session_jurisprudence_evidence(
            retrieval=retrieval,
            applicability=applicability,
            normative_relation_records=normative_relation_records,
            temporal_records=temporal_records,
            ratio_records=ratio_records,
            applicable_normative_refs=applicable_normative_refs,
            query_date=query_date,
        )
        evidence = list(evidence_integration.authorized_evidence_refs)
    else:
        applicable_pages = {
            (assessment.document_id, assessment.page_number)
            for assessment in applicability
            if assessment.applicable_candidate
        }
        evidence = [
            (
                f"{hit.document_id}:page={hit.page_number};score={hit.score:.3f};"
                f"sha256={hit.source_sha256}"
            )
            for hit in retrieval.hits
            if (hit.document_id, hit.page_number) in applicable_pages
        ]

    return SessionJurisprudenceHybridResult(
        retrieval=retrieval,
        applicability=applicability,
        relations=relations,
        evidence_integration=evidence_integration,
        evidence=evidence,
        requires_human_review=(
            relations.requires_human_review
            or any(item.requires_human_review for item in applicability)
            or (
                evidence_integration.requires_human_review
                if evidence_integration is not None
                else False
            )
        ),
    )
