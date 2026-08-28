import pytest

from app.domain.cbr import (
    CaseStatus,
    CBRMatch,
    CBRReuseDecision,
)
from app.services.cbr_reasoning import assess_case_reuse, revise_case_resolution


def match(
    *,
    status: CaseStatus = CaseStatus.ACTIVE,
    refs: list[str] | None = None,
) -> CBRMatch:
    return CBRMatch(
        rank=1,
        case_id="CASE-001",
        status=status,
        similarity=0.9,
        resolution_summary="Resolución de prueba.",
        normative_refs=["NORM-2026"] if refs is None else refs,
        source_refs=["SRC"],
        field_scores=[],
        explanation="Coincidencias principales.",
        requires_human_review=status != CaseStatus.ACTIVE,
    )


def test_active_case_with_shared_norm_is_eligible() -> None:
    result = assess_case_reuse(
        match(),
        current_normative_refs={"NORM-2026"},
    )
    assert result.decision == CBRReuseDecision.ELIGIBLE
    assert result.requires_human_review is False


def test_historical_case_requires_review() -> None:
    result = assess_case_reuse(
        match(status=CaseStatus.HISTORICAL),
        current_normative_refs={"NORM-2026"},
    )
    assert result.decision == CBRReuseDecision.REVIEW_REQUIRED
    assert result.requires_human_review is True


def test_no_shared_norm_requires_review() -> None:
    result = assess_case_reuse(
        match(),
        current_normative_refs={"OTHER"},
    )
    assert result.decision == CBRReuseDecision.REVIEW_REQUIRED


def test_revision_requires_human_confirmation() -> None:
    with pytest.raises(ValueError):
        revise_case_resolution(
            match(),
            revised_summary="Revisión.",
            reviewer_confirmed=False,
        )


def test_case_without_normative_refs_requires_review() -> None:
    result = assess_case_reuse(
        match(refs=[]),
        current_normative_refs={"NORM-2026"},
    )
    assert result.decision == CBRReuseDecision.REVIEW_REQUIRED
    assert result.requires_human_review is True
