import pytest

from app.domain.hybrid_coordination import (
    HybridCoordinationContext,
    HybridReasoningRelation,
)
from app.domain.hybrid_reasoning import NormalizedReasoningResult, ReasoningSource
from app.services.hybrid_reasoning_coordinator import coordinate_rbs_cbr


def _rbs(
    conclusion: str | None = "Existe obligación fiscal.",
    *,
    review: bool = False,
) -> NormalizedReasoningResult:
    return NormalizedReasoningResult(
        reasoning_source=ReasoningSource.RBS,
        conclusion=conclusion,
        legal_basis=["CFF:ART-1"],
        applicability=True if conclusion else False,
        requires_review=review,
        trace=["RULE_001@1.0:obligation"],
    )


def _cbr(
    conclusion: str | None = "Existe obligación fiscal.",
    *,
    basis: list[str] | None = None,
    applicability: bool | None = True,
    review: bool = False,
) -> NormalizedReasoningResult:
    return NormalizedReasoningResult(
        reasoning_source=ReasoningSource.CBR,
        conclusion=conclusion,
        legal_basis=["CFF:ART-1"] if basis is None else basis,
        confidence=0.91 if conclusion else None,
        applicability=applicability,
        requires_review=review,
        trace=["1:CASE-001:similarity=0.9100"],
    )


def test_confirmation_preserves_rbs_as_canonical_conclusion() -> None:
    result = coordinate_rbs_cbr(_rbs(), _cbr())

    assert result.relation == HybridReasoningRelation.CONFIRMATION
    assert result.conclusion == "Existe obligación fiscal."
    assert result.controlling_source == "rbs"
    assert result.shared_legal_basis == ["CFF:ART-1"]
    assert result.requires_review is False


def test_contradiction_never_allows_cbr_to_displace_rbs() -> None:
    result = coordinate_rbs_cbr(
        _rbs("Existe obligación fiscal."),
        _cbr("No existe obligación fiscal."),
    )

    assert result.relation == HybridReasoningRelation.CONTRADICTION
    assert result.conclusion == "Existe obligación fiscal."
    assert result.controlling_source == "rbs"
    assert result.requires_review is True


def test_different_legal_basis_corrects_cbr_reuse_without_changing_rbs() -> None:
    result = coordinate_rbs_cbr(_rbs(), _cbr(basis=["LIVA:ART-1"]))

    assert result.relation == HybridReasoningRelation.CORRECTION
    assert result.conclusion == "Existe obligación fiscal."
    assert result.shared_legal_basis == []
    assert result.requires_review is False


def test_missing_or_inapplicable_cbr_is_insufficient_not_a_contradiction() -> None:
    result = coordinate_rbs_cbr(
        _rbs(),
        _cbr(None, basis=[], applicability=False),
    )

    assert result.relation == HybridReasoningRelation.INSUFFICIENT_EVIDENCE
    assert result.conclusion == "Existe obligación fiscal."
    assert result.requires_review is False


def test_missing_rbs_conclusion_requires_review_and_cbr_cannot_control() -> None:
    result = coordinate_rbs_cbr(_rbs(None), _cbr())

    assert result.relation == HybridReasoningRelation.INSUFFICIENT_EVIDENCE
    assert result.conclusion is None
    assert result.controlling_source is None
    assert result.requires_review is True


def test_explicit_exception_is_never_inferred_from_free_text() -> None:
    ordinary = coordinate_rbs_cbr(
        _rbs("Aplica la regla general."),
        _cbr("Existe una excepción.", basis=["CFF:ART-1"]),
    )
    exception = coordinate_rbs_cbr(
        _rbs("Aplica la regla general."),
        _cbr("Existe una excepción.", basis=["CFF:ART-1"]),
        context=HybridCoordinationContext(
            exception_supported=True,
            exception_basis=["CFF:ART-5"],
        ),
    )

    assert ordinary.relation == HybridReasoningRelation.CONTRADICTION
    assert exception.relation == HybridReasoningRelation.EXCEPTION
    assert exception.requires_review is True
    assert "CFF:ART-5" in exception.reasons[-1]


def test_existing_review_signal_stops_automatic_coordination() -> None:
    result = coordinate_rbs_cbr(_rbs(review=True), _cbr())

    assert result.relation == HybridReasoningRelation.HUMAN_REVIEW
    assert result.requires_review is True
    assert result.conclusion == "Existe obligación fiscal."


def test_trace_preserves_both_reasoning_sources_and_relation() -> None:
    result = coordinate_rbs_cbr(_rbs(), _cbr())

    assert result.trace == [
        "coordination:relation=confirmation",
        "rbs:RULE_001@1.0:obligation",
        "cbr:1:CASE-001:similarity=0.9100",
    ]


def test_source_order_is_enforced() -> None:
    with pytest.raises(ValueError, match="primer resultado"):
        coordinate_rbs_cbr(_cbr(), _cbr())
