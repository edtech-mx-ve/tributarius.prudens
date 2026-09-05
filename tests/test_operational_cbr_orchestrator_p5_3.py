from app.domain.orchestration import (
    OrchestrationStage,
    StageStatus,
)
from app.domain.query import QueryAnalysis, QueryIntent
from app.services.multidimensional_query_analysis import (
    analyze_query_multidimensional,
)
from tests.test_cbr_hybrid_integration import request
from tests.test_hybrid_orchestrator import (
    FakeRetriever,
    orchestrator,
    retrieval,
)


def test_orchestrator_auto_activates_cbr_when_analysis_is_sufficient() -> None:
    query = (
        "Obligaciones de ISR de una persona fisica por "
        "servicios profesionales en 2026"
    )

    multidimensional = analyze_query_multidimensional(
        normalized_query=query,
        primary_intent=QueryIntent.IDENTIFY_OBLIGATIONS,
        secondary_intents=[],
        facts=[],
    )

    query_analysis = QueryAnalysis(
        original_query=query,
        normalized_query=query,
        primary_intent=QueryIntent.IDENTIFY_OBLIGATIONS,
        multidimensional=multidimensional,
        requires_clarification=False,
    )

    result = orchestrator(
        FakeRetriever(retrieval()),
        query_analysis,
    ).run(
        request().model_copy(
            update={
                "query": query,
                "query_fiscal_year": 2026,
                "cbr_query": None,
            }
        )
    )

    cbr_trace = next(
        trace
        for trace in result.traces
        if trace.stage == OrchestrationStage.CBR
    )

    assert cbr_trace.status is StageStatus.DEGRADED
    assert (
        "CBR activado desde QueryAnalysis"
        in cbr_trace.detail
    )

    coordination_trace = next(
        trace
        for trace in result.traces
        if trace.stage == OrchestrationStage.HYBRID_COORDINATION
    )

    assert coordination_trace.status is StageStatus.DEGRADED
    assert result.cbr_reasoning is not None
    assert result.hybrid_coordination is not None
