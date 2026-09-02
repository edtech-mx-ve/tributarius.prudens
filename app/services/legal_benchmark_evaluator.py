from __future__ import annotations

from collections.abc import Iterable

from app.domain.golden_legal_case import GoldenLegalCase
from app.domain.legal_benchmark_evaluation import (
    LegalBenchmarkCheck,
    LegalBenchmarkEvaluation,
)
from app.domain.legal_decision import LegalDecision

_LLM_CONTROLLING_SOURCES = frozenset({"llama", "llm", "legal_hypothesis"})


def _check(
    *,
    name: str,
    passed: bool,
    expected: object,
    observed: object,
) -> LegalBenchmarkCheck:
    return LegalBenchmarkCheck(
        name=name,
        passed=passed,
        expected=str(expected),
        observed=str(observed),
    )


def _normalized_controller(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip().casefold()


def evaluate_golden_case(
    case: GoldenLegalCase,
    decision: LegalDecision,
    *,
    retrieved_document_ids: Iterable[str] = (),
) -> LegalBenchmarkEvaluation:
    """Evalúa solo expectativas explícitas del caso dorado.

    No juzga semánticamente una conclusión cuando el dataset todavía no contiene
    un oráculo jurídico experto para esa conclusión.
    """

    checks: list[LegalBenchmarkCheck] = []
    expectation = case.expectation
    retrieved = set(retrieved_document_ids)

    for document_id in expectation.primary_document_ids:
        checks.append(
            _check(
                name=f"primary_document:{document_id}",
                passed=document_id in retrieved,
                expected=True,
                observed=document_id in retrieved,
            )
        )

    for document_id in expectation.supporting_document_ids:
        checks.append(
            _check(
                name=f"supporting_document:{document_id}",
                passed=document_id in retrieved,
                expected=True,
                observed=document_id in retrieved,
            )
        )

    controller = _normalized_controller(decision.controlling_source)
    if expectation.allowed_controlling_sources:
        allowed = {
            value.strip().casefold()
            for value in expectation.allowed_controlling_sources
        }
        checks.append(
            _check(
                name="controlling_source",
                passed=(
                    controller in allowed
                    and controller not in _LLM_CONTROLLING_SOURCES
                ),
                expected=expectation.allowed_controlling_sources,
                observed=decision.controlling_source,
            )
        )
    else:
        checks.append(
            _check(
                name="controlling_source_not_llm",
                passed=controller not in _LLM_CONTROLLING_SOURCES,
                expected="not llama/llm/legal_hypothesis",
                observed=decision.controlling_source,
            )
        )

    if expectation.requires_human_review is not None:
        checks.append(
            _check(
                name="requires_human_review",
                passed=(
                    decision.requires_human_review
                    is expectation.requires_human_review
                ),
                expected=expectation.requires_human_review,
                observed=decision.requires_human_review,
            )
        )

    if expectation.conclusion_required is not None:
        has_conclusion = decision.conclusion is not None
        checks.append(
            _check(
                name="conclusion_required",
                passed=has_conclusion is expectation.conclusion_required,
                expected=expectation.conclusion_required,
                observed=has_conclusion,
            )
        )

    passed_checks = sum(check.passed for check in checks)
    total_checks = len(checks)
    score = passed_checks / total_checks if total_checks else 1.0

    return LegalBenchmarkEvaluation(
        case_id=case.case_id,
        checks=checks,
        passed_checks=passed_checks,
        total_checks=total_checks,
        score=score,
        passed=passed_checks == total_checks,
    )
