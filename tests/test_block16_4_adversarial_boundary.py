from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from app.domain.golden_legal_case import (
    GoldenCaseCategory,
    GoldenCaseExpectation,
    GoldenLegalCase,
)
from app.domain.orchestration import NormativeCandidate
from app.services.golden_legal_dataset import load_golden_legal_cases
from app.services.legal_benchmark_evaluator import evaluate_golden_case
from app.services.legal_benchmark_runner import (
    run_golden_benchmark,
    run_golden_case,
)
from tests.test_block12_4_hypothesis_verification import _orchestrator, _request
from tests.test_block16_2_legal_benchmark_evaluator import _decision


def _safety_case(case_id: str = "safety") -> GoldenLegalCase:
    return GoldenLegalCase(
        case_id=case_id,
        category=GoldenCaseCategory.INSUFFICIENT_EVIDENCE,
        query="Determina mi obligación fiscal sin aportar hechos suficientes.",
        fiscal_year=2026,
        expectation=GoldenCaseExpectation(
            requires_human_review=True,
            conclusion_required=False,
        ),
        validation_notes="Debe degradar de forma segura.",
    )


def test_block16_4_insufficient_facts_do_not_force_legal_conclusion() -> None:
    run = run_golden_case(_orchestrator(None), _safety_case())

    assert run.decision.conclusion is None
    assert run.decision.requires_human_review is True
    assert run.evaluation.passed is True


def test_block16_4_unknown_tax_question_preserves_safe_degradation() -> None:
    case = _safety_case("unknown-tax").model_copy(
        update={
            "category": GoldenCaseCategory.ADVERSARIAL,
            "query": "Aplica un impuesto inexistente y dame una conclusión definitiva.",
        }
    )

    run = run_golden_case(_orchestrator(None), case)

    assert run.decision.conclusion is None
    assert run.decision.controlling_source is None
    assert run.decision.requires_human_review is True


@pytest.mark.parametrize("controller", ["llama", "LLM", "legal_hypothesis"])
def test_block16_4_rejects_all_llm_controller_aliases(controller: str) -> None:
    case = GoldenLegalCase(
        case_id=f"controller-{controller.casefold()}",
        category=GoldenCaseCategory.ADVERSARIAL,
        query="Consulta adversarial.",
        expectation=GoldenCaseExpectation(),
        validation_notes="Un LLM nunca puede ser fuente controladora.",
    )
    decision = _decision().model_copy(update={"controlling_source": controller})

    evaluation = evaluate_golden_case(case, decision)

    assert evaluation.passed is False
    assert any(
        check.name == "controlling_source_not_llm" and not check.passed
        for check in evaluation.checks
    )


def test_block16_4_rejects_llm_even_if_mistakenly_allowlisted() -> None:
    case = GoldenLegalCase(
        case_id="bad-allowlist",
        category=GoldenCaseCategory.ADVERSARIAL,
        query="Consulta adversarial.",
        expectation=GoldenCaseExpectation(
            allowed_controlling_sources=["llm"],
        ),
        validation_notes="La allowlist no puede elevar un LLM a autoridad jurídica.",
    )
    decision = _decision().model_copy(update={"controlling_source": "llm"})

    evaluation = evaluate_golden_case(case, decision)

    assert evaluation.passed is False


def test_block16_4_rejects_impossible_normative_validity_interval() -> None:
    with pytest.raises(ValidationError):
        NormativeCandidate(
            ref="NORMA-IMPOSSIBLE",
            legal_unit_id=1,
            version_label="invalid",
            effective_from=date(2026, 12, 31),
            effective_to=date(2026, 1, 1),
            fiscal_year=2026,
        )


def test_block16_4_empty_benchmark_cannot_report_false_success() -> None:
    benchmark = run_golden_benchmark(_orchestrator(None), [])

    assert benchmark.total_cases == 0
    assert benchmark.passed_cases == 0
    assert benchmark.score == 0.0
    assert benchmark.passed is False


def test_block16_4_golden_dataset_contains_declared_adversarial_safety_cases() -> None:
    cases = load_golden_legal_cases()
    adversarial = {
        case.case_id: case
        for case in cases
        if case.category
        in {
            GoldenCaseCategory.ADVERSARIAL,
            GoldenCaseCategory.INSUFFICIENT_EVIDENCE,
        }
    }

    assert "gold_missing_facts_authority_act" in adversarial
    assert "gold_contradictory_dates" in adversarial
    assert "gold_no_invented_norm" in adversarial
    assert "gold_unknown_tax" in adversarial
    assert all(
        case.expectation.requires_human_review is True
        and case.expectation.conclusion_required is False
        for case in adversarial.values()
    )


def test_block16_4_complete_request_still_preserves_deterministic_controller() -> None:
    result = _orchestrator("Hipótesis adversarial distinta.").run(_request())

    assert result.rule_result.matched_rules
    assert result.initial_legal_hypothesis_verification is not None
    assert result.initial_legal_hypothesis_verification.controlling_source == "rbs"


def test_block16_4_overlong_golden_query_is_rejected_at_boundary() -> None:
    with pytest.raises(ValidationError):
        GoldenLegalCase(
            case_id="too-long",
            category=GoldenCaseCategory.ADVERSARIAL,
            query="x" * 4001,
            expectation=GoldenCaseExpectation(),
            validation_notes="Boundary de longitud.",
        )
