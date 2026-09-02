from app.domain.jurisprudence import (
    JurisprudenceStatus,
    NormRelationType,
)
from app.domain.jurisprudence_applicability import (
    SessionJurisprudenceApplicabilityAssessment,
)
from app.domain.jurisprudence_relations import JurisprudenceComparisonType
from app.services.jurisprudence_relations import (
    analyze_jurisprudence_relations,
    classify_jurisprudence_relation,
)


def _assessment(
    *,
    applicable_candidate: bool = True,
    relevant_to_problem: bool = True,
    relevant_to_norm: bool = True,
    relation: NormRelationType = NormRelationType.UNKNOWN,
    status: JurisprudenceStatus = JurisprudenceStatus.UNKNOWN,
    review: bool = True,
    reasons: list[str] | None = None,
) -> SessionJurisprudenceApplicabilityAssessment:
    return SessionJurisprudenceApplicabilityAssessment(
        document_id="jurisprudencia-test",
        page_number=1,
        applicable_candidate=applicable_candidate,
        relevant_to_problem=relevant_to_problem,
        relevant_to_norm=relevant_to_norm,
        shared_normative_refs=["CFF:22"] if relevant_to_norm else [],
        criterion_status=status,
        relation_type=relation,
        requires_human_review=review,
        reasons=reasons or [],
    )


def test_interpreting_applicable_criterion_is_concordant() -> None:
    result = classify_jurisprudence_relation(
        _assessment(relation=NormRelationType.INTERPRETS)
    )

    assert result.relation is JurisprudenceComparisonType.CONCORDANT
    assert result.requires_human_review is True


def test_complementary_applicable_criterion_is_concordant() -> None:
    result = classify_jurisprudence_relation(
        _assessment(relation=NormRelationType.COMPLEMENTS)
    )

    assert result.relation is JurisprudenceComparisonType.CONCORDANT


def test_explicit_conflict_is_contradictory_and_reviewable() -> None:
    result = classify_jurisprudence_relation(
        _assessment(relation=NormRelationType.CONFLICTS)
    )

    assert result.relation is JurisprudenceComparisonType.CONTRADICTORY
    assert result.requires_human_review is True
    assert "explicit_normative_conflict" in result.reasons


def test_non_applicable_candidate_is_distinguishable() -> None:
    result = classify_jurisprudence_relation(
        _assessment(
            applicable_candidate=False,
            relevant_to_problem=False,
            relation=NormRelationType.INTERPRETS,
            reasons=["matter_mismatch"],
        )
    )

    assert result.relation is JurisprudenceComparisonType.DISTINGUISHABLE
    assert "candidate_not_applicable_to_problem" in result.reasons


def test_unknown_relation_is_not_promoted_to_concordance() -> None:
    result = classify_jurisprudence_relation(_assessment())

    assert result.relation is JurisprudenceComparisonType.UNDETERMINED
    assert result.requires_human_review is True


def test_analysis_preserves_all_relation_classes() -> None:
    result = analyze_jurisprudence_relations(
        [
            _assessment(relation=NormRelationType.INTERPRETS),
            _assessment(
                applicable_candidate=False,
                relevant_to_problem=False,
                relation=NormRelationType.COMPLEMENTS,
            ),
            _assessment(relation=NormRelationType.CONFLICTS),
            _assessment(relation=NormRelationType.UNKNOWN),
        ]
    )

    assert result.concordant_count == 1
    assert result.distinguishable_count == 1
    assert result.contradictory_count == 1
    assert result.undetermined_count == 1
    assert result.has_conflict is True
    assert result.requires_human_review is True


def test_empty_analysis_is_safe_and_non_conflicting() -> None:
    result = analyze_jurisprudence_relations([])

    assert result.assessments == []
    assert result.has_conflict is False
    assert result.requires_human_review is False
