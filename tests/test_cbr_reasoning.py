import pytest

from app.domain.cbr import (
    CaseStatus,
    CBRMatch,
    CBRReuseAssessment,
    CBRReuseDecision,
)
from app.services.cbr_reasoning import (
    MINIMUM_REUSE_SIMILARITY,
    assess_case_reuse,
    revise_case_resolution,
)


def match(
    *,
    status: CaseStatus = CaseStatus.ACTIVE,
    refs: list[str] | None = None,
    similarity: float = 0.9,
    requires_human_review: bool | None = None,
) -> CBRMatch:
    review = (
        status != CaseStatus.ACTIVE
        if requires_human_review is None
        else requires_human_review
    )
    return CBRMatch(
        rank=1,
        case_id="CASE-001",
        status=status,
        similarity=similarity,
        resolution_summary="Resolución de prueba.",
        normative_refs=["NORM-2026"] if refs is None else refs,
        source_refs=["SRC"],
        field_scores=[],
        explanation="Coincidencias principales.",
        requires_human_review=review,
    )


def test_reuse_threshold_is_explicit() -> None:
    assert MINIMUM_REUSE_SIMILARITY == 0.75


def test_active_case_with_shared_norm_is_eligible() -> None:
    result = assess_case_reuse(match(), current_normative_refs={"NORM-2026"})
    assert result.decision == CBRReuseDecision.ELIGIBLE
    assert result.requires_human_review is False


def test_similarity_below_reuse_threshold_is_rejected() -> None:
    result = assess_case_reuse(
        match(similarity=0.74),
        current_normative_refs={"NORM-2026"},
    )
    assert result.decision == CBRReuseDecision.REJECTED


def test_historical_case_requires_review() -> None:
    result = assess_case_reuse(
        match(status=CaseStatus.HISTORICAL),
        current_normative_refs={"NORM-2026"},
    )
    assert result.decision == CBRReuseDecision.REVIEW_REQUIRED


def test_revision_requires_human_confirmation() -> None:
    with pytest.raises(ValueError):
        revise_case_resolution(
            match(),
            revised_summary="Resolución adaptada.",
            reviewer_confirmed=False,
        )


def test_rejected_case_cannot_be_adapted() -> None:
    source = match()
    assessment = CBRReuseAssessment(
        case_id=source.case_id,
        decision=CBRReuseDecision.REJECTED,
        shared_normative_refs=[],
        reason="Rechazado.",
        requires_human_review=True,
    )
    with pytest.raises(ValueError, match="rechazado"):
        revise_case_resolution(
            source,
            revised_summary="Resolución adaptada.",
            reviewer_confirmed=True,
            reuse_assessment=assessment,
        )


def test_assessment_must_belong_to_same_case() -> None:
    source = match()
    assessment = CBRReuseAssessment(
        case_id="CASE-OTHER",
        decision=CBRReuseDecision.ELIGIBLE,
        shared_normative_refs=["NORM-2026"],
        reason="Elegible.",
        requires_human_review=False,
    )
    with pytest.raises(ValueError, match="no corresponde"):
        revise_case_resolution(
            source,
            revised_summary="Resolución adaptada.",
            reviewer_confirmed=True,
            reuse_assessment=assessment,
        )


@pytest.mark.parametrize(
    "status",
    [CaseStatus.SUPERSEDED, CaseStatus.INVALIDATED],
)
def test_disabled_case_cannot_be_adapted(status: CaseStatus) -> None:
    with pytest.raises(ValueError, match="no puede adaptarse"):
        revise_case_resolution(
            match(status=status, requires_human_review=False),
            revised_summary="Resolución adaptada.",
            reviewer_confirmed=True,
        )


def test_weak_match_cannot_be_adapted() -> None:
    with pytest.raises(ValueError, match="similitud"):
        revise_case_resolution(
            match(similarity=MINIMUM_REUSE_SIMILARITY - 0.01),
            revised_summary="Resolución adaptada.",
            reviewer_confirmed=True,
        )


def test_adaptation_must_record_real_change() -> None:
    source = match()
    with pytest.raises(ValueError, match="cambio explícito"):
        revise_case_resolution(
            source,
            revised_summary="  Resolución de prueba.  ",
            reviewer_confirmed=True,
        )


def test_controlled_adaptation_preserves_source_case_id() -> None:
    source = match()
    assessment = assess_case_reuse(
        source,
        current_normative_refs={"NORM-2026"},
    )
    revision = revise_case_resolution(
        source,
        revised_summary="Resolución adaptada al caso actual.",
        reviewer_confirmed=True,
        reuse_assessment=assessment,
    )
    assert revision.source_case_id == source.case_id
    assert revision.reviewer_confirmed is True
    assert revision.revised_resolution_summary == "Resolución adaptada al caso actual."
