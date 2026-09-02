from __future__ import annotations

from app.domain.golden_legal_case import GoldenLegalCase
from app.domain.legal_benchmark_quality import (
    LegalBenchmarkAcceptanceStatus,
    LegalBenchmarkQualityReport,
)
from app.domain.legal_benchmark_run import LegalBenchmarkRun

_LLM_CONTROLLERS = frozenset({"llama", "llm", "legal_hypothesis"})


def _rate(passed: int, total: int) -> float:
    return passed / total if total else 0.0


def build_legal_benchmark_quality_report(
    cases: list[GoldenLegalCase],
    benchmark: LegalBenchmarkRun,
) -> LegalBenchmarkQualityReport:
    """Consolida métricas observadas sin convertir ausencia de evidencia en éxito."""

    dataset_ids = [case.case_id for case in cases]
    executed_ids = [item.case_id for item in benchmark.cases]
    dataset_coverage_complete = (
        bool(dataset_ids)
        and len(executed_ids) == len(dataset_ids)
        and set(executed_ids) == set(dataset_ids)
    )

    passed_case_count = sum(item.evaluation.passed for item in benchmark.cases)
    executed_case_count = len(benchmark.cases)
    failed_case_count = executed_case_count - passed_case_count

    total_checks = sum(item.evaluation.total_checks for item in benchmark.cases)
    passed_checks = sum(item.evaluation.passed_checks for item in benchmark.cases)
    failed_checks = total_checks - passed_checks

    case_by_id = {case.case_id: case for case in cases}
    expected_review_ids = {
        case.case_id
        for case in cases
        if case.expectation.requires_human_review is True
    }
    human_review_correct_cases = sum(
        item.case_id in expected_review_ids
        and item.decision.requires_human_review is True
        for item in benchmark.cases
    )
    human_review_expected_cases = len(expected_review_ids)
    human_review_pass_rate = (
        _rate(human_review_correct_cases, human_review_expected_cases)
        if human_review_expected_cases
        else None
    )

    llm_controller_violations = sum(
        (item.decision.controlling_source or "").strip().casefold()
        in _LLM_CONTROLLERS
        for item in benchmark.cases
    )

    integrity_complete = all(
        item.decision.schema_version == "1.0"
        and item.decision.source_analysis_schema_version == "1.0"
        and item.evaluation.case_id == item.case_id
        for item in benchmark.cases
    )

    reasons: list[str] = []
    if not cases or not benchmark.cases:
        status = LegalBenchmarkAcceptanceStatus.NO_EVIDENCE
        reasons.append("No existe ejecución suficiente para aceptar el benchmark.")
    else:
        if not dataset_coverage_complete:
            reasons.append("La ejecución no cubre exactamente todo el dataset dorado.")
        if failed_case_count:
            reasons.append(f"Existen {failed_case_count} casos de benchmark fallidos.")
        if llm_controller_violations:
            reasons.append(
                f"Existen {llm_controller_violations} violaciones de controlador LLM."
            )
        if not integrity_complete:
            reasons.append("La integridad estructural del resultado no es completa.")
        if (
            human_review_pass_rate is not None
            and human_review_pass_rate < 1.0
        ):
            reasons.append("No todos los casos que exigen revisión humana fueron escalados.")

        status = (
            LegalBenchmarkAcceptanceStatus.ACCEPTED
            if not reasons
            else LegalBenchmarkAcceptanceStatus.REJECTED
        )

    limitations = [
        "Los casos sin oráculo jurídico experto no validan equivalencia semántica "
        "de la conclusión.",
        "El benchmark valida expectativas explícitas del dataset y no sustituye "
        "revisión jurídica experta.",
    ]
    if any(
        case.expectation.conclusion_required is None
        for case in cases
    ):
        limitations.append(
            "Parte del dataset conserva expectativas de recuperación sin exigir "
            "una conclusión jurídica."
        )
    if any(case.fiscal_year is None for case in cases):
        limitations.append(
            "Existen casos sin año fiscal explícito y dependen del contrato temporal "
            "de ejecución."
        )

    del case_by_id

    return LegalBenchmarkQualityReport(
        dataset_case_count=len(cases),
        executed_case_count=executed_case_count,
        passed_case_count=passed_case_count,
        failed_case_count=failed_case_count,
        case_pass_rate=_rate(passed_case_count, executed_case_count),
        total_checks=total_checks,
        passed_checks=passed_checks,
        failed_checks=failed_checks,
        check_pass_rate=_rate(passed_checks, total_checks),
        human_review_expected_cases=human_review_expected_cases,
        human_review_correct_cases=human_review_correct_cases,
        human_review_pass_rate=human_review_pass_rate,
        llm_controller_violations=llm_controller_violations,
        integrity_complete=integrity_complete,
        dataset_coverage_complete=dataset_coverage_complete,
        acceptance_status=status,
        acceptance_reasons=reasons,
        known_limitations=limitations,
    )
