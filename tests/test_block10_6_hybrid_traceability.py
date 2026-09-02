from datetime import UTC, datetime

from app.domain.hybrid_coordination import (
    HybridCoordinationFactors,
    HybridCoordinationResult,
    HybridReasoningRelation,
)
from app.domain.hybrid_reasoning import NormalizedReasoningResult, ReasoningSource
from app.domain.traceability import CanonicalExecutionResult
from app.services.traceability import build_canonical_result, verify_canonical_integrity
from tests.test_traceability import build_result


def _reasoning(source: ReasoningSource, trace: list[str]) -> NormalizedReasoningResult:
    return NormalizedReasoningResult(
        reasoning_source=source,
        conclusion="La obligación fiscal resulta aplicable.",
        legal_basis=["CFF:ART-1"],
        applicability=True,
        trace=trace,
    )


def _coordination(*, review: bool = False) -> HybridCoordinationResult:
    return HybridCoordinationResult(
        relation=(
            HybridReasoningRelation.CONTRADICTION
            if review
            else HybridReasoningRelation.CONFIRMATION
        ),
        conclusion="La obligación fiscal resulta aplicable.",
        controlling_source="rbs",
        rbs_result=_reasoning(ReasoningSource.RBS, ["rule:RBS-001"]),
        cbr_result=_reasoning(ReasoningSource.CBR, ["case:CBR-001"]),
        factors=HybridCoordinationFactors(
            rbs_has_conclusion=True,
            rbs_applicability=True,
            cbr_applicability=True,
            cbr_similarity=0.91,
            cbr_temporal_context="ACTIVE",
            shared_legal_basis_count=1,
            normative_priority_preserved=True,
        ),
        shared_legal_basis=["CFF:ART-1"],
        reasons=["RBS y CBR fueron contrastados de forma explícita."],
        requires_review=review,
        trace=["coordination:relation=confirmation"],
    )


def _canonical(*, review: bool = False) -> CanonicalExecutionResult:
    request, result = build_result()
    result = result.model_copy(
        update={"hybrid_coordination": _coordination(review=review)}
    )
    return build_canonical_result(
        request,
        result,
        now=datetime(2026, 9, 2, 12, 0, tzinfo=UTC),
    )


def test_canonical_result_preserves_complete_hybrid_decision() -> None:
    canonical = _canonical()
    decision = canonical.hybrid_coordination

    assert decision is not None
    assert decision["relation"] == "confirmation"
    assert decision["controlling_source"] == "rbs"
    assert decision["shared_legal_basis"] == ["CFF:ART-1"]
    assert decision["factors"]["cbr_similarity"] == 0.91
    assert decision["factors"]["normative_priority_preserved"] is True


def test_traceability_exposes_structured_hybrid_decision() -> None:
    trace = _canonical().traceability.hybrid_decision

    assert trace is not None
    assert trace.relation == "confirmation"
    assert trace.controlling_source == "rbs"
    assert trace.rbs_trace == ["rule:RBS-001"]
    assert trace.cbr_trace == ["case:CBR-001"]
    assert trace.reasons == ["RBS y CBR fueron contrastados de forma explícita."]


def test_hybrid_review_becomes_explicit_uncertainty() -> None:
    canonical = _canonical(review=True)
    uncertainty = next(
        item
        for item in canonical.traceability.uncertainties
        if item.code == "HYBRID_COORDINATION_REVIEW"
    )

    assert uncertainty.stage == "hybrid_coordination"
    assert uncertainty.requires_human_review is True
    assert canonical.traceability.hybrid_decision is not None
    assert canonical.traceability.hybrid_decision.requires_human_review is True


def test_hybrid_decision_is_covered_by_canonical_integrity_hash() -> None:
    canonical = _canonical()
    assert verify_canonical_integrity(canonical) is True

    assert canonical.hybrid_coordination is not None
    canonical.hybrid_coordination["controlling_source"] = "cbr"
    assert verify_canonical_integrity(canonical) is False


def test_absent_hybrid_coordination_remains_backward_compatible() -> None:
    request, result = build_result()
    canonical = build_canonical_result(request, result)

    assert canonical.hybrid_coordination is None
    assert canonical.traceability.hybrid_decision is None
    assert verify_canonical_integrity(canonical) is True
