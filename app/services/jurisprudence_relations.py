from __future__ import annotations

from app.domain.jurisprudence import NormRelationType
from app.domain.jurisprudence_applicability import (
    SessionJurisprudenceApplicabilityAssessment,
)
from app.domain.jurisprudence_relations import (
    JurisprudenceComparisonType,
    JurisprudenceConflictAnalysis,
    JurisprudenceRelationAssessment,
)


def classify_jurisprudence_relation(
    assessment: SessionJurisprudenceApplicabilityAssessment,
) -> JurisprudenceRelationAssessment:
    """Clasifica la relación sin resolver automáticamente conflictos jurídicos."""

    reasons = list(assessment.reasons)
    shared_refs = list(assessment.shared_normative_refs)

    if assessment.relation_type is NormRelationType.CONFLICTS:
        relation = JurisprudenceComparisonType.CONTRADICTORY
        reasons.append("explicit_normative_conflict")
        review = True
    elif not assessment.applicable_candidate:
        relation = JurisprudenceComparisonType.DISTINGUISHABLE
        reasons.append("candidate_not_applicable_to_problem")
        review = assessment.requires_human_review
    elif assessment.relation_type in {
        NormRelationType.INTERPRETS,
        NormRelationType.COMPLEMENTS,
    }:
        relation = JurisprudenceComparisonType.CONCORDANT
        reasons.append(f"relation_{assessment.relation_type.value}")
        review = assessment.requires_human_review
    else:
        relation = JurisprudenceComparisonType.UNDETERMINED
        reasons.append("relation_not_established")
        review = True

    return JurisprudenceRelationAssessment(
        document_id=assessment.document_id,
        relation=relation,
        normative_relation=assessment.relation_type,
        shared_normative_refs=shared_refs,
        reasons=list(dict.fromkeys(reasons)),
        requires_human_review=review,
    )


def analyze_jurisprudence_relations(
    assessments: list[SessionJurisprudenceApplicabilityAssessment],
) -> JurisprudenceConflictAnalysis:
    """Resume concordancias, distinciones y contradicciones conservadoramente."""

    classified = [
        classify_jurisprudence_relation(assessment) for assessment in assessments
    ]

    concordant = sum(
        item.relation is JurisprudenceComparisonType.CONCORDANT for item in classified
    )
    distinguishable = sum(
        item.relation is JurisprudenceComparisonType.DISTINGUISHABLE
        for item in classified
    )
    contradictory = sum(
        item.relation is JurisprudenceComparisonType.CONTRADICTORY
        for item in classified
    )
    undetermined = sum(
        item.relation is JurisprudenceComparisonType.UNDETERMINED
        for item in classified
    )

    return JurisprudenceConflictAnalysis(
        assessments=classified,
        concordant_count=concordant,
        distinguishable_count=distinguishable,
        contradictory_count=contradictory,
        undetermined_count=undetermined,
        has_conflict=contradictory > 0,
        requires_human_review=(
            contradictory > 0
            or undetermined > 0
            or any(item.requires_human_review for item in classified)
        ),
    )
