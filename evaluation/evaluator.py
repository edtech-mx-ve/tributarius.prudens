from __future__ import annotations

from collections.abc import Mapping

from app.domain.traceability import CanonicalExecutionResult
from evaluation.metrics import exact_match, mean, recall_at_k, set_precision, set_recall
from evaluation.models import (
    CaseEvaluationResult,
    EvaluationCase,
    EvaluationThresholds,
    IntegralEvaluationReport,
    MetricResult,
)


def _actual_rule_ids(result: CanonicalExecutionResult) -> list[str]:
    matched = result.rules.get("matched_rules", [])
    if not isinstance(matched, list):
        return []
    return [
        str(item["rule_id"])
        for item in matched
        if isinstance(item, dict) and item.get("rule_id")
    ]


def _actual_citations(result: CanonicalExecutionResult) -> list[str]:
    explanation = result.explanation
    if not isinstance(explanation, dict):
        return []
    answer = explanation.get("answer")
    if not isinstance(answer, dict):
        return []
    evidence_ids = answer.get("evidence_ids", [])
    if not isinstance(evidence_ids, list):
        return []
    return [str(item) for item in evidence_ids]


def _actual_retrieved_ids(result: CanonicalExecutionResult) -> list[str]:
    hits = result.retrieval.get("hits", [])
    if not isinstance(hits, list):
        return []
    return [
        str(item["chunk_id"])
        for item in hits
        if isinstance(item, dict) and item.get("chunk_id")
    ]


def _actual_normative_refs(result: CanonicalExecutionResult) -> list[str]:
    refs = result.normative.get("applicable_refs", [])
    if not isinstance(refs, list):
        return []
    return [str(item) for item in refs]


def _calculation_value(result: CanonicalExecutionResult, path: str) -> str | None:
    current: object = result.calculations
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return None if current is None else str(current)


def trace_consistency(result: CanonicalExecutionResult) -> float:
    evidence_ids = {item.ref_id for item in result.traceability.evidence}
    event_refs = {
        ref
        for event in result.traceability.events
        for ref in event.evidence_refs
    }
    citations = set(_actual_citations(result))
    if not citations.issubset(evidence_ids):
        return 0.0
    if not event_refs.issubset(evidence_ids):
        return 0.0
    if result.traceability.execution_id != result.execution_id:
        return 0.0
    if result.traceability.folio != result.folio:
        return 0.0
    return 1.0


def evaluate_case(
    case: EvaluationCase,
    result: CanonicalExecutionResult,
    *,
    top_k: int = 5,
) -> CaseEvaluationResult:
    metrics: dict[str, float] = {}
    failures: list[str] = []

    if case.expected_intent is not None:
        actual_intent = str(result.query_analysis.get("primary_intent", ""))
        metrics["intent_accuracy"] = exact_match(case.expected_intent, actual_intent)

    if case.expected_relevant_chunk_ids:
        metrics["retrieval_recall_at_k"] = recall_at_k(
            case.expected_relevant_chunk_ids,
            _actual_retrieved_ids(result),
            k=top_k,
        )

    expected_citations = (
        case.expected_evidence_ids
        if case.expected_evidence_ids
        else case.expected_relevant_chunk_ids
    )
    if expected_citations:
        actual_citations = _actual_citations(result)
        metrics["citation_precision"] = set_precision(
            expected_citations,
            actual_citations,
        )
        metrics["citation_recall"] = set_recall(
            expected_citations,
            actual_citations,
        )

    if case.expected_applicable_normative_refs:
        metrics["normative_accuracy"] = exact_match(
            set(case.expected_applicable_normative_refs),
            set(_actual_normative_refs(result)),
        )

    if case.expected_rule_ids:
        metrics["rule_accuracy"] = exact_match(
            set(case.expected_rule_ids),
            set(_actual_rule_ids(result)),
        )

    if case.expected_calculations:
        calculation_checks = [
            exact_match(expected, _calculation_value(result, path))
            for path, expected in case.expected_calculations.items()
        ]
        metrics["calculation_accuracy"] = mean(calculation_checks)

    metrics["review_accuracy"] = exact_match(
        case.expect_human_review,
        result.traceability.requires_human_review,
    )
    actual_abstention = (
        result.explanation is None
        or result.traceability.requires_human_review
        and not _actual_normative_refs(result)
    )
    metrics["abstention_accuracy"] = exact_match(
        case.expect_abstention,
        actual_abstention,
    )
    metrics["trace_consistency"] = trace_consistency(result)

    thresholds = EvaluationThresholds()
    for name, value in metrics.items():
        threshold = float(getattr(thresholds, name))
        if value < threshold:
            failures.append(
                f"{name}={value:.4f}<threshold={threshold:.4f}"
            )

    return CaseEvaluationResult(
        case_id=case.case_id,
        passed=not failures,
        metrics=metrics,
        failures=failures,
        tags=case.tags,
    )


def evaluate_integral(
    cases: list[EvaluationCase],
    results: Mapping[str, CanonicalExecutionResult],
    *,
    dataset_id: str,
    dataset_sha256: str,
    thresholds: EvaluationThresholds | None = None,
    top_k: int = 5,
) -> IntegralEvaluationReport:
    if not cases:
        raise ValueError("Se requiere al menos un caso.")
    thresholds = thresholds or EvaluationThresholds()
    case_results: list[CaseEvaluationResult] = []
    for case in cases:
        result = results.get(case.case_id)
        if result is None:
            case_results.append(
                CaseEvaluationResult(
                    case_id=case.case_id,
                    passed=False,
                    metrics={},
                    failures=["missing_result"],
                    tags=case.tags,
                )
            )
            continue
        case_results.append(evaluate_case(case, result, top_k=top_k))

    metric_names = sorted(
        {name for item in case_results for name in item.metrics}
    )
    metric_results: list[MetricResult] = []
    for name in metric_names:
        values = [
            item.metrics[name]
            for item in case_results
            if name in item.metrics
        ]
        value = mean(values)
        threshold = float(getattr(thresholds, name))
        metric_results.append(
            MetricResult(
                name=name,
                value=value,
                threshold=threshold,
                passed=value >= threshold,
            )
        )

    overall = (
        all(metric.passed for metric in metric_results)
        and all(item.passed for item in case_results)
        and len(case_results) == len(cases)
    )
    return IntegralEvaluationReport(
        dataset_id=dataset_id,
        dataset_sha256=dataset_sha256,
        case_count=len(cases),
        passed_case_count=sum(item.passed for item in case_results),
        overall_passed=overall,
        metrics=metric_results,
        cases=case_results,
        limitations=[
            "La fidelidad semántica de afirmaciones no se infiere solo de IDs de cita.",
            "Las fixtures sintéticas validan el pipeline, no exactitud jurídica real.",
            "La evaluación LLM real requiere un modelo Llama y dataset humano validado.",
            "Jurisprudencia se evalúa en los Sprints 17 y 18.",
        ],
    )
