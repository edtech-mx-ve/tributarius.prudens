from __future__ import annotations

from app.domain.hybrid_coordination import (
    HybridCoordinationFactors,
    HybridCoordinationResult,
    HybridReasoningRelation,
)
from app.domain.hybrid_reasoning import NormalizedReasoningResult, ReasoningSource
from app.domain.orchestration import OrchestrationStage, StageStatus
from app.services.legal_heuristics_stage import run_legal_heuristics_stage


def _coordination(
    *,
    relation: HybridReasoningRelation = HybridReasoningRelation.CONFIRMATION,
    requires_review: bool = False,
    rbs_legal_basis: list[str] | None = None,
) -> HybridCoordinationResult:
    rbs = NormalizedReasoningResult(
        reasoning_source=ReasoningSource.RBS,
        conclusion="Conclusión normativa",
        legal_basis=rbs_legal_basis if rbs_legal_basis is not None else ["CFF:1"],
        applicability=True,
    )
    cbr = NormalizedReasoningResult(
        reasoning_source=ReasoningSource.CBR,
        conclusion="Conclusión normativa",
        legal_basis=["CFF:1"],
        applicability=True,
        confidence=0.9,
    )
    return HybridCoordinationResult(
        relation=relation,
        conclusion="Conclusión normativa",
        controlling_source="rbs",
        rbs_result=rbs,
        cbr_result=cbr,
        factors=HybridCoordinationFactors(
            rbs_has_conclusion=True,
            rbs_applicability=True,
            cbr_applicability=True,
            cbr_similarity=0.9,
            shared_legal_basis_count=1,
            normative_priority_preserved=True,
        ),
        shared_legal_basis=["CFF:1"],
        requires_review=requires_review,
    )


def test_stage_is_skipped_without_hybrid_coordination() -> None:
    evaluation, trace, review = run_legal_heuristics_stage(None)

    assert evaluation is None
    assert trace.stage == OrchestrationStage.LEGAL_HEURISTICS
    assert trace.status == StageStatus.SKIPPED
    assert review is False


def test_stage_preserves_canonical_hybrid_decision() -> None:
    coordination = _coordination()

    evaluation, trace, review = run_legal_heuristics_stage(coordination)

    assert evaluation is not None
    assert evaluation.canonical_conclusion == coordination.conclusion
    assert evaluation.controlling_source == coordination.controlling_source
    assert evaluation.normative_priority_preserved is True
    assert trace.stage == OrchestrationStage.LEGAL_HEURISTICS
    assert trace.status == StageStatus.COMPLETED
    assert review is False


def test_stage_propagates_heuristic_review_without_changing_conclusion() -> None:
    coordination = _coordination(rbs_legal_basis=[])

    evaluation, trace, review = run_legal_heuristics_stage(coordination)

    assert evaluation is not None
    assert evaluation.requires_review is True
    assert evaluation.canonical_conclusion == "Conclusión normativa"
    assert evaluation.controlling_source == "rbs"
    assert trace.status == StageStatus.DEGRADED
    assert review is True


def test_hybrid_review_is_preserved_by_heuristic_stage() -> None:
    coordination = _coordination(
        relation=HybridReasoningRelation.CONTRADICTION,
        requires_review=True,
    )

    evaluation, trace, review = run_legal_heuristics_stage(coordination)

    assert evaluation is not None
    assert evaluation.requires_review is True
    assert trace.status == StageStatus.DEGRADED
    assert review is True
