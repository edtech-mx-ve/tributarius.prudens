from __future__ import annotations

from app.domain.jurisprudence_document import JurisprudenceDocumentRepresentation
from app.domain.jurisprudence_extraction import JurisprudenceExtractedMetadata
from app.domain.jurisprudence_hybrid import SessionJurisprudenceHybridResult
from app.services.jurisprudence_applicability import (
    assess_session_jurisprudence_applicability,
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
) -> SessionJurisprudenceHybridResult:
    """Ejecuta recuperación, aplicabilidad y relaciones de jurisprudencia temporal."""

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
        evidence=evidence,
        requires_human_review=(
            relations.requires_human_review
            or any(item.requires_human_review for item in applicability)
        ),
    )
