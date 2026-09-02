from app.domain.hybrid_coordination import (
    HybridCoordinationContext,
    HybridReasoningRelation,
)
from app.domain.hybrid_reasoning import NormalizedReasoningResult, ReasoningSource
from app.services.hybrid_reasoning_coordinator import coordinate_rbs_cbr


def _rbs(
    conclusion: str | None = "Procede la obligación fiscal.",
    *,
    basis: list[str] | None = None,
    review: bool = False,
) -> NormalizedReasoningResult:
    return NormalizedReasoningResult(
        reasoning_source=ReasoningSource.RBS,
        conclusion=conclusion,
        legal_basis=basis or ["CFF:ART-1"],
        applicability=bool(conclusion),
        requires_review=review,
        trace=["RULE-001@1.0:obligation"],
    )


def _cbr(
    conclusion: str | None = "Procede la obligación fiscal.",
    *,
    basis: list[str] | None = None,
    similarity: float | None = 0.92,
    applicability: bool | None = True,
    temporal_context: str | None = "active",
    review: bool = False,
) -> NormalizedReasoningResult:
    return NormalizedReasoningResult(
        reasoning_source=ReasoningSource.CBR,
        conclusion=conclusion,
        legal_basis=["CFF:ART-1"] if basis is None else basis,
        confidence=similarity,
        applicability=applicability,
        temporal_context=temporal_context,
        requires_review=review,
        trace=["1:CASE-001:similarity=0.9200"],
    )


def test_agreement_is_confirmation_and_preserves_normative_priority() -> None:
    result = coordinate_rbs_cbr(_rbs(), _cbr())

    assert result.relation == HybridReasoningRelation.CONFIRMATION
    assert result.controlling_source == "rbs"
    assert result.factors.normative_priority_preserved is True
    assert result.factors.shared_legal_basis_count == 1
    assert result.factors.cbr_similarity == 0.92


def test_contradiction_requires_review_without_cbr_displacing_rbs() -> None:
    result = coordinate_rbs_cbr(
        _rbs("Procede la obligación fiscal."),
        _cbr("No procede la obligación fiscal."),
    )

    assert result.relation == HybridReasoningRelation.CONTRADICTION
    assert result.conclusion == "Procede la obligación fiscal."
    assert result.controlling_source == "rbs"
    assert result.requires_review is True
    assert result.factors.normative_priority_preserved is True


def test_historical_case_is_exposed_as_human_review_context() -> None:
    result = coordinate_rbs_cbr(
        _rbs(),
        _cbr(temporal_context="historical", review=True),
    )

    assert result.relation == HybridReasoningRelation.HUMAN_REVIEW
    assert result.factors.cbr_temporal_context == "historical"
    assert result.factors.cbr_requires_review is True
    assert result.controlling_source == "rbs"


def test_insufficient_similarity_cannot_be_promoted_to_confirmation() -> None:
    result = coordinate_rbs_cbr(
        _rbs(),
        _cbr(similarity=0.41, applicability=False, review=True),
    )

    assert result.relation == HybridReasoningRelation.HUMAN_REVIEW
    assert result.factors.cbr_similarity == 0.41
    assert result.factors.cbr_applicability is False
    assert result.controlling_source == "rbs"


def test_different_normative_basis_corrects_experiential_reuse() -> None:
    result = coordinate_rbs_cbr(
        _rbs(basis=["CFF:ART-1"]),
        _cbr(basis=["LIVA:ART-1"]),
    )

    assert result.relation == HybridReasoningRelation.CORRECTION
    assert result.shared_legal_basis == []
    assert result.factors.shared_legal_basis_count == 0
    assert result.conclusion == "Procede la obligación fiscal."


def test_exception_requires_explicit_context_and_never_overwrites_rbs() -> None:
    result = coordinate_rbs_cbr(
        _rbs("Aplica la regla general."),
        _cbr("El caso presenta una excepción."),
        context=HybridCoordinationContext(
            exception_supported=True,
            exception_basis=["CFF:ART-5"],
        ),
    )

    assert result.relation == HybridReasoningRelation.EXCEPTION
    assert result.conclusion == "Aplica la regla general."
    assert result.controlling_source == "rbs"
    assert result.requires_review is True


def test_absent_rbs_conclusion_never_allows_cbr_to_become_controller() -> None:
    result = coordinate_rbs_cbr(_rbs(None), _cbr())

    assert result.relation == HybridReasoningRelation.INSUFFICIENT_EVIDENCE
    assert result.controlling_source is None
    assert result.conclusion is None
    assert result.requires_review is True
    assert result.factors.rbs_has_conclusion is False
    assert result.factors.normative_priority_preserved is True
