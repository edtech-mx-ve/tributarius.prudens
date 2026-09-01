from datetime import date
from decimal import Decimal

from app.domain.cbr import (
    CaseStatus,
    CBRCase,
    CBRQuery,
    CBRReuseDecision,
)
from app.domain.orchestration import (
    HybridOrchestrationRequest,
    OrchestrationStage,
    StageStatus,
)
from app.services.hybrid_orchestrator import HybridOrchestrator
from llm.providers.mock import MockLLMProvider
from llm.service import LlamaRAGService
from tests.test_hybrid_orchestrator import (
    FakeAnalyzer,
    FakeRetriever,
    analysis,
    candidate,
    isr_input,
    retrieval,
    rules,
    tariff,
)


def cbr_query() -> CBRQuery:
    return CBRQuery(
        taxpayer_type="individual",
        activity="servicios profesionales",
        tax="ISR",
        problem_type="determinacion de obligaciones",
        procedural_stage="orientacion",
        fiscal_year=2026,
    )


def cbr_case(
    *,
    case_id: str = "CASE-CBR-001",
    activity: str = "servicios profesionales",
    procedural_stage: str = "orientacion",
    normative_refs: list[str] | None = None,
) -> CBRCase:
    return CBRCase(
        case_id=case_id,
        status=CaseStatus.ACTIVE,
        taxpayer_type="individual",
        activity=activity,
        tax="ISR",
        problem_type="determinacion de obligaciones",
        procedural_stage=procedural_stage,
        fiscal_year=2026,
        resolution_summary="Caso CBR de integración.",
        normative_refs=(
            ["NORM_TEST_ISR_2026"]
            if normative_refs is None
            else normative_refs
        ),
        source_refs=["CBR_INTEGRATION_TEST"],
    )


def service(cases: list[CBRCase]) -> HybridOrchestrator:
    return HybridOrchestrator(
        query_analyzer=FakeAnalyzer(analysis()),
        retriever=FakeRetriever(retrieval()),
        llm_service=LlamaRAGService(MockLLMProvider()),
        rule_set=rules(),
        isr_tariff=tariff(),
        cbr_cases=cases,
    )


def request() -> HybridOrchestrationRequest:
    return HybridOrchestrationRequest(
        query="Calcula ISR",
        query_date=date(2026, 8, 28),
        query_fiscal_year=2026,
        normative_candidates=[candidate()],
        isr_input=isr_input(),
        cbr_query=cbr_query(),
    )


def test_eligible_cbr_case_is_integrated_without_overriding_norm_or_isr() -> None:
    result = service([cbr_case()]).run(request())

    assert result.cbr_result is not None
    assert result.cbr_result.returned_count == 1
    assert len(result.cbr_reuse_assessments) == 1
    assert (
        result.cbr_reuse_assessments[0].decision
        == CBRReuseDecision.ELIGIBLE
    )
    assert result.cbr_reuse_assessments[0].requires_human_review is False

    # CBR remains experiential support. It cannot rewrite legal applicability.
    assert result.applicable_normative_refs == ["NORM_TEST_ISR_2026"]

    # Nor can it alter the deterministic calculation authorized by RBR.
    assert result.isr_result is not None
    assert result.isr_result.final_tax == Decimal("2300.00")

    cbr_trace = next(
        item for item in result.traces
        if item.stage == OrchestrationStage.CBR
    )
    assert cbr_trace.status == StageStatus.COMPLETED


def test_retrieved_but_weak_case_is_rejected_and_propagates_review() -> None:
    # Critical fields still match, so the case survives the retrieval gate.
    # Activity + procedural-stage mismatch lowers similarity below the
    # stricter 0.75 reuse threshold while remaining above retrieval 0.60.
    weak = cbr_case(
        case_id="CASE-CBR-WEAK",
        activity="actividad comercial distinta",
        procedural_stage="fiscalizacion",
    )

    result = service([weak]).run(request())

    assert result.cbr_result is not None
    assert result.cbr_result.returned_count == 1
    match = result.cbr_result.matches[0]
    assert 0.60 <= match.similarity < 0.75

    assessment = result.cbr_reuse_assessments[0]
    assert assessment.decision == CBRReuseDecision.REJECTED
    assert assessment.requires_human_review is True
    assert result.requires_human_review is True

    # Rejection of experiential reuse must not erase normative/RBR outputs.
    assert result.applicable_normative_refs == ["NORM_TEST_ISR_2026"]
    assert result.isr_result is not None
    assert result.isr_result.final_tax == Decimal("2300.00")


def test_case_without_shared_norm_requires_review_but_does_not_replace_norm() -> None:
    foreign_norm = cbr_case(
        case_id="CASE-CBR-OTHER-NORM",
        normative_refs=["NORM_OTHER"],
    )

    result = service([foreign_norm]).run(request())

    assert result.cbr_result is not None
    assert result.cbr_result.returned_count == 1

    assessment = result.cbr_reuse_assessments[0]
    assert assessment.decision == CBRReuseDecision.REVIEW_REQUIRED
    assert assessment.shared_normative_refs == []
    assert assessment.requires_human_review is True
    assert result.requires_human_review is True

    assert result.applicable_normative_refs == ["NORM_TEST_ISR_2026"]
    assert result.isr_result is not None
    assert result.isr_result.final_tax == Decimal("2300.00")


def test_requested_cbr_without_case_corpus_degrades_safely() -> None:
    result = service([]).run(request())

    assert result.cbr_result is None
    assert result.cbr_reuse_assessments == []
    assert result.requires_human_review is True

    cbr_trace = next(
        item for item in result.traces
        if item.stage == OrchestrationStage.CBR
    )
    assert cbr_trace.status == StageStatus.DEGRADED

    # Controlled degradation preserves the deterministic legal pipeline.
    assert result.applicable_normative_refs == ["NORM_TEST_ISR_2026"]
    assert result.isr_result is not None
    assert result.isr_result.final_tax == Decimal("2300.00")
