from app.domain.hybrid_coordination import HybridReasoningRelation
from app.domain.orchestration import OrchestrationStage, StageStatus
from tests.test_cbr_hybrid_integration import cbr_case, request, service
from tests.test_hybrid_orchestrator import analysis, orchestrator, retrieval


def test_orchestrator_exposes_normalized_rbs_without_cbr_coordination() -> None:
    fake_retriever = retrieval()
    # Reuse the canonical no-CBR fixture path from the orchestrator tests.
    from tests.test_hybrid_orchestrator import FakeRetriever

    result = orchestrator(FakeRetriever(fake_retriever), analysis()).run(
        request().model_copy(update={"cbr_query": None})
    )

    assert result.rbs_reasoning is not None
    assert result.cbr_reasoning is None
    assert result.hybrid_coordination is None
    coordination_trace = next(
        trace
        for trace in result.traces
        if trace.stage == OrchestrationStage.HYBRID_COORDINATION
    )
    assert coordination_trace.status == StageStatus.SKIPPED


def test_orchestrator_coordinates_rbs_and_cbr_and_preserves_rbs_control() -> None:
    result = service([cbr_case()]).run(request())

    assert result.rbs_reasoning is not None
    assert result.cbr_reasoning is not None
    assert result.hybrid_coordination is not None
    assert result.hybrid_coordination.controlling_source == "rbs"
    assert result.hybrid_coordination.conclusion == result.rbs_reasoning.conclusion
    assert result.hybrid_coordination.relation in {
        HybridReasoningRelation.CONFIRMATION,
        HybridReasoningRelation.CORRECTION,
        HybridReasoningRelation.CONTRADICTION,
        HybridReasoningRelation.HUMAN_REVIEW,
    }


def test_requested_cbr_without_cases_produces_reviewable_coordination() -> None:
    result = service([]).run(request())

    assert result.hybrid_coordination is not None
    assert result.hybrid_coordination.requires_review is True
    assert result.requires_human_review is True
    assert result.hybrid_coordination.relation == HybridReasoningRelation.HUMAN_REVIEW
