import json
from pathlib import Path

from app.domain.traceability import CanonicalExecutionResult
from evaluation.dataset import load_evaluation_dataset
from evaluation.error_analysis import analyze_errors
from evaluation.evaluator import evaluate_case, evaluate_integral, trace_consistency


def canonical_fixture() -> CanonicalExecutionResult:
    payload = json.loads(
        Path("traceability/fixtures/trace_test.json").read_text(encoding="utf-8")
    )
    return CanonicalExecutionResult.model_validate(payload)


def test_integral_happy_path_passes_all_metrics() -> None:
    cases, digest = load_evaluation_dataset(
        Path("evaluation/datasets/integral_smoke.json")
    )
    result = canonical_fixture()
    report = evaluate_integral(
        cases,
        {"EVAL-ISR-001": result},
        dataset_id="integral-smoke-v1",
        dataset_sha256=digest,
    )
    assert report.overall_passed is True
    assert report.passed_case_count == 1
    assert all(metric.value == 1.0 for metric in report.metrics)


def test_wrong_citation_is_detected() -> None:
    cases, _ = load_evaluation_dataset(
        Path("evaluation/datasets/integral_smoke.json")
    )
    result = canonical_fixture()
    assert result.explanation is not None
    result.explanation["answer"]["evidence_ids"] = ["invented-chunk"]
    evaluated = evaluate_case(cases[0], result)
    assert evaluated.passed is False
    assert evaluated.metrics["citation_precision"] == 0.0
    assert evaluated.metrics["trace_consistency"] == 0.0


def test_wrong_normative_reference_is_detected() -> None:
    cases, _ = load_evaluation_dataset(
        Path("evaluation/datasets/integral_smoke.json")
    )
    result = canonical_fixture()
    result.normative["applicable_refs"] = ["WRONG_NORM"]
    evaluated = evaluate_case(cases[0], result)
    assert evaluated.metrics["normative_accuracy"] == 0.0


def test_wrong_calculation_is_detected() -> None:
    cases, _ = load_evaluation_dataset(
        Path("evaluation/datasets/integral_smoke.json")
    )
    result = canonical_fixture()
    result.calculations["isr"]["final_tax"] = "9999.00"
    evaluated = evaluate_case(cases[0], result)
    assert evaluated.metrics["calculation_accuracy"] == 0.0


def test_trace_consistency_rejects_unknown_event_ref() -> None:
    result = canonical_fixture()
    result.traceability.events[0].evidence_refs.append("UNKNOWN-REF")
    assert trace_consistency(result) == 0.0


def test_missing_result_is_reported() -> None:
    cases, digest = load_evaluation_dataset(
        Path("evaluation/datasets/integral_smoke.json")
    )
    report = evaluate_integral(
        cases,
        {},
        dataset_id="integral-smoke-v1",
        dataset_sha256=digest,
    )
    assert report.overall_passed is False
    assert report.cases[0].failures == ["missing_result"]
    analysis = analyze_errors(report)
    assert analysis.buckets[0].code == "missing_result"
