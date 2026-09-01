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
from app.services.cbr_reasoning import assess_case_reuse
from app.services.cbr_traceability import build_cbr_reasoning_trace
from app.services.hybrid_orchestrator import HybridOrchestrator
from cbr.engine import retrieve_similar_cases
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


def query() -> CBRQuery:
    return CBRQuery(
        taxpayer_type="individual",
        activity="servicios profesionales",
        tax="ISR",
        problem_type="determinacion de obligaciones",
        procedural_stage="orientacion",
        fiscal_year=2026,
    )


def case(
    *,
    case_id: str,
    status: CaseStatus = CaseStatus.ACTIVE,
    activity: str = "servicios profesionales",
    tax: str = "ISR",
    problem_type: str = "determinacion de obligaciones",
    procedural_stage: str = "orientacion",
    normative_refs: list[str] | None = None,
) -> CBRCase:
    return CBRCase(
        case_id=case_id,
        status=status,
        taxpayer_type="individual",
        activity=activity,
        tax=tax,
        problem_type=problem_type,
        procedural_stage=procedural_stage,
        fiscal_year=2026,
        resolution_summary="Caso fiscal sintético de evaluación integral.",
        normative_refs=(
            ["NORM_TEST_ISR_2026"]
            if normative_refs is None
            else normative_refs
        ),
        source_refs=[f"SOURCE-{case_id}"],
    )


def orchestrator(cases: list[CBRCase]) -> HybridOrchestrator:
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
        cbr_query=query(),
    )


def test_block7_end_to_end_eligible_case_preserves_legal_pipeline() -> None:
    service = orchestrator([case(case_id="CASE-B7-ELIGIBLE")])
    result = service.run(request())

    assert result.cbr_result is not None
    assert result.cbr_result.returned_count == 1
    assert result.cbr_result.matches[0].case_id == "CASE-B7-ELIGIBLE"

    assessment = result.cbr_reuse_assessments[0]
    assert assessment.decision == CBRReuseDecision.ELIGIBLE
    assert assessment.requires_human_review is False
    assert assessment.shared_normative_refs == ["NORM_TEST_ISR_2026"]

    trace = build_cbr_reasoning_trace(
        result.cbr_result,
        result.cbr_reuse_assessments,
    )
    assert trace.returned_count == 1
    assert trace.cases[0].case_id == "CASE-B7-ELIGIBLE"
    assert trace.cases[0].reuse_decision == CBRReuseDecision.ELIGIBLE
    assert trace.requires_human_review is False

    assert result.applicable_normative_refs == ["NORM_TEST_ISR_2026"]
    assert result.rule_result.matched_rules[0].rule_id == "ISR_RULE_001"
    assert result.isr_result is not None
    assert result.isr_result.final_tax == Decimal("2300.00")


def test_block7_weak_experience_is_rejected_without_corrupting_outputs() -> None:
    weak = case(
        case_id="CASE-B7-WEAK",
        activity="actividad comercial distinta",
        procedural_stage="fiscalizacion",
    )
    result = orchestrator([weak]).run(request())

    assert result.cbr_result is not None
    assert result.cbr_result.returned_count == 1
    assert 0.60 <= result.cbr_result.matches[0].similarity < 0.75

    assessment = result.cbr_reuse_assessments[0]
    assert assessment.decision == CBRReuseDecision.REJECTED
    assert assessment.requires_human_review is True
    assert result.requires_human_review is True

    trace = build_cbr_reasoning_trace(
        result.cbr_result,
        result.cbr_reuse_assessments,
    )
    assert trace.requires_human_review is True
    assert trace.cases[0].reuse_decision == CBRReuseDecision.REJECTED

    assert result.applicable_normative_refs == ["NORM_TEST_ISR_2026"]
    assert result.isr_result is not None
    assert result.isr_result.final_tax == Decimal("2300.00")


def test_block7_unshared_normative_context_requires_review() -> None:
    foreign = case(
        case_id="CASE-B7-FOREIGN-NORM",
        normative_refs=["NORM_OTHER"],
    )
    result = orchestrator([foreign]).run(request())

    assert result.cbr_result is not None
    assessment = result.cbr_reuse_assessments[0]
    assert assessment.decision == CBRReuseDecision.REVIEW_REQUIRED
    assert assessment.shared_normative_refs == []
    assert assessment.requires_human_review is True
    assert result.requires_human_review is True

    assert result.applicable_normative_refs == ["NORM_TEST_ISR_2026"]
    assert result.isr_result is not None
    assert result.isr_result.final_tax == Decimal("2300.00")


def test_block7_retrieval_rejects_critical_field_mismatch() -> None:
    wrong_tax = case(
        case_id="CASE-B7-WRONG-TAX",
        tax="IVA",
    )
    result = retrieve_similar_cases(query(), [wrong_tax])

    assert result.candidate_count == 1
    assert result.returned_count == 0
    assert result.matches == []


def test_block7_historical_case_never_becomes_silent_authority() -> None:
    historical = case(
        case_id="CASE-B7-HISTORICAL",
        status=CaseStatus.HISTORICAL,
    )
    retrieval_result = retrieve_similar_cases(query(), [historical])

    assert retrieval_result.returned_count == 1
    assessment = assess_case_reuse(
        retrieval_result.matches[0],
        current_normative_refs={"NORM_TEST_ISR_2026"},
    )
    assert assessment.decision == CBRReuseDecision.REVIEW_REQUIRED
    assert assessment.requires_human_review is True


def test_block7_missing_case_corpus_degrades_without_losing_determinism() -> None:
    result = orchestrator([]).run(request())

    assert result.cbr_result is None
    assert result.cbr_reuse_assessments == []
    assert result.requires_human_review is True

    cbr_trace = next(
        item
        for item in result.traces
        if item.stage == OrchestrationStage.CBR
    )
    assert cbr_trace.status == StageStatus.DEGRADED

    assert result.applicable_normative_refs == ["NORM_TEST_ISR_2026"]
    assert result.rule_result.matched_rules[0].rule_id == "ISR_RULE_001"
    assert result.isr_result is not None
    assert result.isr_result.final_tax == Decimal("2300.00")
