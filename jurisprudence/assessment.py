from __future__ import annotations

from datetime import date

from app.domain.jurisprudence import (
    JurisprudenceCandidateAssessment,
    JurisprudenceMetadata,
    JurisprudenceStatus,
    NormRelationType,
)


def assess_jurisprudential_candidate(
    metadata: JurisprudenceMetadata,
    *,
    query_date: date,
    applicable_normative_refs: set[str],
    matter: str | None = None,
) -> JurisprudenceCandidateAssessment:
    """Evalúa elegibilidad operativa sin declarar que un criterio resuelve el caso."""

    reasons: list[str] = []
    review = False

    if not metadata.verified:
        reasons.append("metadata_not_verified")
        return JurisprudenceCandidateAssessment(
            document_id=metadata.document_id,
            identifier=metadata.identifier,
            eligible=False,
            relevant_to_norm=False,
            relation_type=metadata.relation_type,
            requires_human_review=True,
            reasons=reasons,
        )

    if metadata.publication_date > query_date:
        reasons.append("published_after_query_date")
        return JurisprudenceCandidateAssessment(
            document_id=metadata.document_id,
            identifier=metadata.identifier,
            eligible=False,
            relevant_to_norm=False,
            relation_type=metadata.relation_type,
            requires_human_review=True,
            reasons=reasons,
        )

    if metadata.status in {
        JurisprudenceStatus.SUPERSEDED,
        JurisprudenceStatus.INVALIDATED,
    }:
        reasons.append(f"status_{metadata.status.value}")
        return JurisprudenceCandidateAssessment(
            document_id=metadata.document_id,
            identifier=metadata.identifier,
            eligible=False,
            relevant_to_norm=False,
            relation_type=metadata.relation_type,
            requires_human_review=True,
            reasons=reasons,
        )

    if metadata.status in {
        JurisprudenceStatus.HISTORICAL,
        JurisprudenceStatus.UNKNOWN,
    }:
        review = True
        reasons.append(f"status_{metadata.status.value}")

    shared = set(metadata.related_normative_refs) & applicable_normative_refs
    relevant_to_norm = bool(shared)
    if metadata.related_normative_refs and not relevant_to_norm:
        review = True
        reasons.append("no_shared_normative_ref")

    if metadata.relation_type in {
        NormRelationType.CONFLICTS,
        NormRelationType.UNKNOWN,
    }:
        review = True
        reasons.append(f"relation_{metadata.relation_type.value}")

    if matter is not None and metadata.matter.casefold() != matter.strip().casefold():
        reasons.append("matter_mismatch")
        return JurisprudenceCandidateAssessment(
            document_id=metadata.document_id,
            identifier=metadata.identifier,
            eligible=False,
            relevant_to_norm=relevant_to_norm,
            relation_type=metadata.relation_type,
            requires_human_review=review,
            reasons=reasons,
        )

    if not reasons:
        reasons.append("eligible")

    return JurisprudenceCandidateAssessment(
        document_id=metadata.document_id,
        identifier=metadata.identifier,
        eligible=True,
        relevant_to_norm=relevant_to_norm,
        relation_type=metadata.relation_type,
        requires_human_review=review,
        reasons=reasons,
    )
