from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from app.domain.golden_legal_case import GoldenLegalCase
from app.domain.legal_benchmark_run import LegalBenchmarkCaseRun, LegalBenchmarkRun
from app.domain.orchestration import HybridOrchestrationRequest
from app.services.hybrid_orchestrator import HybridOrchestrator
from app.services.integral_legal_analyzer import build_integral_legal_analysis
from app.services.legal_benchmark_evaluator import evaluate_golden_case
from app.services.legal_decision import build_legal_decision


def _retrieved_document_ids(result: object) -> list[str]:
    retrieval = getattr(result, "retrieval", None)
    hits = getattr(retrieval, "hits", ())
    document_ids: set[str] = set()

    for hit in hits:
        metadata = getattr(hit, "metadata", None)
        document_id = getattr(metadata, "document_id", None)
        if isinstance(document_id, str) and document_id:
            document_ids.add(document_id)

    return sorted(document_ids)


def run_golden_request(
    orchestrator: HybridOrchestrator,
    case: GoldenLegalCase,
    request: HybridOrchestrationRequest,
) -> LegalBenchmarkCaseRun:
    """Ejecuta y evalúa exactamente la solicitud suministrada contra el motor."""

    result = orchestrator.run(request)
    analysis = build_integral_legal_analysis(result)
    decision = build_legal_decision(analysis)
    document_ids = _retrieved_document_ids(result)
    evaluation = evaluate_golden_case(
        case,
        decision,
        retrieved_document_ids=document_ids,
    )
    return LegalBenchmarkCaseRun(
        case_id=case.case_id,
        retrieved_document_ids=document_ids,
        decision=decision,
        evaluation=evaluation,
    )


def run_golden_case(
    orchestrator: HybridOrchestrator,
    case: GoldenLegalCase,
) -> LegalBenchmarkCaseRun:
    """Ejecuta un caso textual autónomo con el mismo contrato temporal del runtime web."""

    request = HybridOrchestrationRequest(
        query=case.query,
        query_date=date.today(),
        query_fiscal_year=case.fiscal_year,
        top_k=5,
    )
    return run_golden_request(orchestrator, case, request)


def run_golden_benchmark(
    orchestrator: HybridOrchestrator,
    cases: Iterable[GoldenLegalCase],
) -> LegalBenchmarkRun:
    runs = [run_golden_case(orchestrator, case) for case in cases]
    passed_cases = sum(item.evaluation.passed for item in runs)
    total_cases = len(runs)
    score = passed_cases / total_cases if total_cases else 0.0
    return LegalBenchmarkRun(
        cases=runs,
        passed_cases=passed_cases,
        total_cases=total_cases,
        score=score,
        passed=total_cases > 0 and passed_cases == total_cases,
    )
