import json
from pathlib import Path

import pytest

from app.domain.traceability import CanonicalExecutionResult
from evaluation.dataset import load_evaluation_dataset
from evaluation.evaluator import evaluate_integral
from evaluation.models import IntegralEvaluationReport
from evaluation.reporting import EvaluationReportError, export_evaluation_report


def report() -> IntegralEvaluationReport:
    cases, digest = load_evaluation_dataset(
        Path("evaluation/datasets/integral_smoke.json")
    )
    payload = json.loads(
        Path("traceability/fixtures/trace_test.json").read_text(encoding="utf-8")
    )
    result = CanonicalExecutionResult.model_validate(payload)
    return evaluate_integral(
        cases,
        {"EVAL-ISR-001": result},
        dataset_id="integral-smoke-v1",
        dataset_sha256=digest,
    )


def test_report_export_is_controlled(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    export_evaluation_report(report(), output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["overall_passed"] is True
    assert payload["error_analysis"]["failed_case_count"] == 0
    with pytest.raises(EvaluationReportError):
        export_evaluation_report(report(), output)


def test_report_requires_json_extension(tmp_path: Path) -> None:
    with pytest.raises(EvaluationReportError):
        export_evaluation_report(report(), tmp_path / "report.txt")
