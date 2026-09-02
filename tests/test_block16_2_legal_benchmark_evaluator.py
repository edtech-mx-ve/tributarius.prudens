from __future__ import annotations

from app.domain.golden_legal_case import (
    GoldenCaseCategory,
    GoldenCaseExpectation,
    GoldenLegalCase,
)
from app.domain.legal_decision import LegalDecision
from app.services.integral_legal_analyzer import build_integral_legal_analysis
from app.services.legal_benchmark_evaluator import evaluate_golden_case
from app.services.legal_decision import build_legal_decision
from tests.test_block12_4_hypothesis_verification import _orchestrator, _request


def _decision() -> LegalDecision:
    result = _orchestrator(None).run(_request())
    analysis = build_integral_legal_analysis(result)
    return build_legal_decision(analysis)


def test_evaluator_scores_explicit_expectations_only() -> None:
    case = GoldenLegalCase(
        case_id="case",
        category=GoldenCaseCategory.NORMATIVE,
        query="Consulta",
        expectation=GoldenCaseExpectation(
            primary_document_ids=["cff"],
            supporting_document_ids=["lfdc"],
            allowed_controlling_sources=["rbs"],
        ),
        validation_notes="Caso de prueba.",
    )

    evaluation = evaluate_golden_case(
        case,
        _decision(),
        retrieved_document_ids=["cff", "lfdc"],
    )

    assert evaluation.total_checks == 3
    assert evaluation.passed_checks == 3
    assert evaluation.score == 1.0
    assert evaluation.passed is True


def test_evaluator_detects_missing_expected_document() -> None:
    case = GoldenLegalCase(
        case_id="case",
        category=GoldenCaseCategory.NORMATIVE,
        query="Consulta",
        expectation=GoldenCaseExpectation(
            primary_document_ids=["cff"],
            allowed_controlling_sources=["rbs"],
        ),
        validation_notes="Caso de prueba.",
    )

    evaluation = evaluate_golden_case(case, _decision())

    assert evaluation.passed is False
    assert evaluation.score < 1.0
    assert any(
        check.name == "primary_document:cff" and not check.passed
        for check in evaluation.checks
    )


def test_evaluator_never_accepts_llm_when_no_controller_oracle_exists() -> None:
    case = GoldenLegalCase(
        case_id="case",
        category=GoldenCaseCategory.ADVERSARIAL,
        query="Consulta",
        expectation=GoldenCaseExpectation(),
        validation_notes="Caso de prueba.",
    )
    decision = _decision()
    decision.controlling_source = "llama"

    evaluation = evaluate_golden_case(case, decision)

    assert evaluation.passed is False
    assert any(
        check.name == "controlling_source_not_llm" and not check.passed
        for check in evaluation.checks
    )


def test_evaluator_checks_review_expectation() -> None:
    case = GoldenLegalCase(
        case_id="case",
        category=GoldenCaseCategory.INSUFFICIENT_EVIDENCE,
        query="Consulta",
        expectation=GoldenCaseExpectation(
            requires_human_review=True,
            conclusion_required=False,
        ),
        validation_notes="Caso de prueba.",
    )
    decision = _decision().model_copy(
        update={"requires_human_review": True, "conclusion": None}
    )

    evaluation = evaluate_golden_case(case, decision)

    assert evaluation.passed is True
    assert evaluation.score == 1.0


def test_evaluator_detects_forced_conclusion_in_insufficient_case() -> None:
    case = GoldenLegalCase(
        case_id="case",
        category=GoldenCaseCategory.INSUFFICIENT_EVIDENCE,
        query="Consulta",
        expectation=GoldenCaseExpectation(
            requires_human_review=True,
            conclusion_required=False,
        ),
        validation_notes="Caso de prueba.",
    )
    decision = _decision().model_copy(
        update={
            "requires_human_review": True,
            "conclusion": "Conclusión no permitida para este caso.",
        }
    )

    evaluation = evaluate_golden_case(case, decision)

    assert evaluation.passed is False
    assert any(
        check.name == "conclusion_required" and not check.passed
        for check in evaluation.checks
    )


def test_evaluator_is_deterministic() -> None:
    case = GoldenLegalCase(
        case_id="case",
        category=GoldenCaseCategory.NORMATIVE,
        query="Consulta",
        expectation=GoldenCaseExpectation(
            allowed_controlling_sources=["rbs"],
        ),
        validation_notes="Caso de prueba.",
    )
    decision = _decision()

    first = evaluate_golden_case(case, decision)
    second = evaluate_golden_case(case, decision)

    assert first == second
