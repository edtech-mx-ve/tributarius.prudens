from __future__ import annotations

from app.domain.golden_legal_case import (
    GoldenCaseCategory,
    GoldenCaseExpectation,
    GoldenLegalCase,
)
from app.domain.legal_benchmark_quality import LegalBenchmarkAcceptanceStatus
from app.domain.legal_benchmark_run import LegalBenchmarkCaseRun, LegalBenchmarkRun
from app.services.legal_benchmark_quality import build_legal_benchmark_quality_report
from app.services.legal_benchmark_runner import run_golden_request
from tests.test_block12_4_hypothesis_verification import _orchestrator, _request


def _case(
    case_id: str = "quality-isr",
    *,
    human_review: bool | None = None,
) -> GoldenLegalCase:
    return GoldenLegalCase(
        case_id=case_id,
        category=GoldenCaseCategory.CALCULATION,
        query="Calcula ISR",
        fiscal_year=2026,
        expectation=GoldenCaseExpectation(
            allowed_controlling_sources=["rbs"],
            requires_human_review=human_review,
        ),
        validation_notes="Caso controlado para informe final.",
    )


def _run(case: GoldenLegalCase) -> LegalBenchmarkCaseRun:
    return run_golden_request(_orchestrator(None), case, _request())


def test_block16_5_accepts_complete_green_benchmark() -> None:
    case = _case()
    run = _run(case)
    benchmark = LegalBenchmarkRun(
        cases=[run],
        passed_cases=1,
        total_cases=1,
        score=1.0,
        passed=True,
    )

    report = build_legal_benchmark_quality_report([case], benchmark)

    assert report.acceptance_status == LegalBenchmarkAcceptanceStatus.ACCEPTED
    assert report.dataset_coverage_complete is True
    assert report.integrity_complete is True
    assert report.case_pass_rate == 1.0
    assert report.check_pass_rate == 1.0
    assert report.llm_controller_violations == 0


def test_block16_5_rejects_failed_case() -> None:
    case = _case().model_copy(
        update={
            "expectation": GoldenCaseExpectation(
                primary_document_ids=["missing-document"],
                allowed_controlling_sources=["rbs"],
            )
        }
    )
    run = _run(case)
    benchmark = LegalBenchmarkRun(
        cases=[run],
        passed_cases=0,
        total_cases=1,
        score=0.0,
        passed=False,
    )

    report = build_legal_benchmark_quality_report([case], benchmark)

    assert report.acceptance_status == LegalBenchmarkAcceptanceStatus.REJECTED
    assert report.failed_case_count == 1
    assert report.failed_checks >= 1


def test_block16_5_rejects_partial_dataset_execution() -> None:
    cases = [_case("one"), _case("two")]
    run = _run(cases[0])
    benchmark = LegalBenchmarkRun(
        cases=[run],
        passed_cases=1,
        total_cases=1,
        score=1.0,
        passed=True,
    )

    report = build_legal_benchmark_quality_report(cases, benchmark)

    assert report.dataset_coverage_complete is False
    assert report.acceptance_status == LegalBenchmarkAcceptanceStatus.REJECTED


def test_block16_5_empty_execution_is_no_evidence_not_success() -> None:
    report = build_legal_benchmark_quality_report(
        [],
        LegalBenchmarkRun(
            cases=[],
            passed_cases=0,
            total_cases=0,
            score=0.0,
            passed=False,
        ),
    )

    assert report.acceptance_status == LegalBenchmarkAcceptanceStatus.NO_EVIDENCE
    assert report.case_pass_rate == 0.0
    assert report.check_pass_rate == 0.0


def test_block16_5_detects_llm_controller_violation_independently() -> None:
    case = _case()
    run = _run(case)
    run.decision.controlling_source = "LLM"
    benchmark = LegalBenchmarkRun(
        cases=[run],
        passed_cases=1,
        total_cases=1,
        score=1.0,
        passed=True,
    )

    report = build_legal_benchmark_quality_report([case], benchmark)

    assert report.llm_controller_violations == 1
    assert report.acceptance_status == LegalBenchmarkAcceptanceStatus.REJECTED


def test_block16_5_requires_all_expected_human_review_escalations() -> None:
    case = _case(human_review=True)
    run = _run(case)
    benchmark = LegalBenchmarkRun(
        cases=[run],
        passed_cases=0,
        total_cases=1,
        score=0.0,
        passed=False,
    )

    report = build_legal_benchmark_quality_report([case], benchmark)

    assert report.human_review_expected_cases == 1
    assert report.human_review_correct_cases == 0
    assert report.human_review_pass_rate == 0.0
    assert report.acceptance_status == LegalBenchmarkAcceptanceStatus.REJECTED


def test_block16_5_reports_known_validation_limits() -> None:
    case = _case()
    report = build_legal_benchmark_quality_report(
        [case],
        LegalBenchmarkRun(
            cases=[_run(case)],
            passed_cases=1,
            total_cases=1,
            score=1.0,
            passed=True,
        ),
    )

    assert report.known_limitations
    assert any("oráculo jurídico experto" in item for item in report.known_limitations)
