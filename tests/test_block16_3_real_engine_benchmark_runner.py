from __future__ import annotations

from app.domain.golden_legal_case import (
    GoldenCaseCategory,
    GoldenCaseExpectation,
    GoldenLegalCase,
)
from app.services.legal_benchmark_runner import (
    run_golden_benchmark,
    run_golden_case,
    run_golden_request,
)
from tests.test_block12_4_hypothesis_verification import (
    _orchestrator,
    _request,
)


def _case() -> GoldenLegalCase:
    return GoldenLegalCase(
        case_id="runtime-isr",
        category=GoldenCaseCategory.CALCULATION,
        query="Calcula ISR",
        fiscal_year=2026,
        expectation=GoldenCaseExpectation(
            allowed_controlling_sources=["rbs"],
        ),
        validation_notes="Prueba de integración contra HybridOrchestrator.",
    )


def test_block16_3_runs_complete_existing_request_through_orchestrator() -> None:
    run = run_golden_request(_orchestrator(None), _case(), _request())

    assert run.case_id == "runtime-isr"
    assert run.decision.conclusion == "Perfil sujeto a revisión ISR."
    assert run.decision.controlling_source == "rbs"
    assert run.evaluation.passed is True


def test_block16_3_builds_analyzer_and_legal_decision_from_runtime_result() -> None:
    run = run_golden_request(_orchestrator(None), _case(), _request())

    assert run.decision.schema_version == "1.0"
    assert run.decision.source_analysis_schema_version == "1.0"
    assert run.decision.reasoning_chain.steps
    assert run.decision.rule_conclusions


def test_block16_3_uses_retrieval_observed_from_runtime() -> None:
    run = run_golden_request(_orchestrator(None), _case(), _request())

    assert run.retrieved_document_ids
    assert run.retrieved_document_ids == sorted(set(run.retrieved_document_ids))


def test_block16_3_text_only_case_preserves_safe_degradation() -> None:
    run = run_golden_case(_orchestrator(None), _case())

    assert run.decision.conclusion is None
    assert run.decision.controlling_source is None
    assert run.decision.requires_human_review is True
    assert run.evaluation.passed is False


def test_block16_3_benchmark_reports_observed_failures() -> None:
    benchmark = run_golden_benchmark(
        _orchestrator(None),
        [_case(), _case().model_copy(update={"case_id": "runtime-isr-2"})],
    )

    assert benchmark.total_cases == 2
    assert benchmark.passed_cases == 0
    assert benchmark.score == 0.0
    assert benchmark.passed is False


def test_block16_3_failed_expectation_is_reported_not_hidden() -> None:
    case = _case().model_copy(
        update={
            "expectation": GoldenCaseExpectation(
                primary_document_ids=["document-that-runtime-did-not-return"],
                allowed_controlling_sources=["rbs"],
            )
        }
    )

    run = run_golden_case(_orchestrator(None), case)

    assert run.evaluation.passed is False
    assert run.evaluation.score < 1.0
    assert any(not check.passed for check in run.evaluation.checks)


def test_block16_3_llm_hypothesis_cannot_control_complete_request() -> None:
    run = run_golden_request(
        _orchestrator("Hipótesis experimental."),
        _case(),
        _request(),
    )

    assert run.decision.controlling_source == "rbs"
    assert run.evaluation.passed is True
