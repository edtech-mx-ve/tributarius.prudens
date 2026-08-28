import json
from pathlib import Path

from app.domain.traceability import CanonicalExecutionResult
from evaluation.evaluator import evaluate_case
from evaluation.models import EvaluationCase, EvaluationCaseKind


def fixture() -> CanonicalExecutionResult:
    payload = json.loads(
        Path("traceability/fixtures/trace_test.json").read_text(encoding="utf-8")
    )
    return CanonicalExecutionResult.model_validate(payload)


def test_expected_abstention_passes_when_no_norm_and_review_required() -> None:
    result = fixture()
    result.normative["applicable_refs"] = []
    result.explanation = None
    result.traceability.requires_human_review = True
    case = EvaluationCase(
        case_id="ABS-001",
        kind=EvaluationCaseKind.ABSTENTION,
        expect_abstention=True,
        expect_human_review=True,
    )
    evaluated = evaluate_case(case, result)
    assert evaluated.metrics["abstention_accuracy"] == 1.0
    assert evaluated.metrics["review_accuracy"] == 1.0


def test_missing_required_abstention_is_detected() -> None:
    case = EvaluationCase(
        case_id="ABS-002",
        kind=EvaluationCaseKind.ABSTENTION,
        expect_abstention=True,
        expect_human_review=True,
    )
    evaluated = evaluate_case(case, fixture())
    assert evaluated.metrics["abstention_accuracy"] == 0.0
    assert evaluated.metrics["review_accuracy"] == 0.0
