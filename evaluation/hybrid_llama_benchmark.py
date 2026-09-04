from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Iterable
from pathlib import Path

from pydantic import ValidationError

from app.domain.hybrid_legal_verification import HybridLegalVerificationState
from app.domain.hybrid_llama_runtime import HybridLlamaRuntimeResult, HybridLlamaRuntimeStatus
from app.domain.jurisprudence_decision_application import JurisprudenceDecisionEffect
from evaluation.hybrid_llama_fixtures import (
    F12BenchmarkProvider,
    build_f12_request,
    build_f12_runtime,
)
from evaluation.hybrid_llama_models import (
    HybridLlamaBenchmarkCaseResult,
    HybridLlamaBenchmarkComparisonCase,
    HybridLlamaBenchmarkProviderKind,
    HybridLlamaBenchmarkProviderReport,
    HybridLlamaBenchmarkReport,
    HybridLlamaBenchmarkScenario,
    HybridLlamaBenchmarkSuite,
    HybridLlamaBenchmarkThresholds,
)

_DEFAULT_SUITE = Path(__file__).resolve().parents[1] / "app" / "resources" / (
    "hybrid_llama_benchmark_suite.json"
)
_METRIC_NAMES = (
    "generation_success",
    "hypothesis_quality",
    "normative_grounding",
    "ratio_fidelity",
    "obiter_separation",
    "rbs_consistency",
    "cbr_consistency",
    "jurisprudence_compliance",
    "argument_consistency",
    "human_review_precision",
    "legal_authority_integrity",
    "single_decision_integrity",
)


class HybridLlamaBenchmarkError(RuntimeError):
    pass


def load_hybrid_llama_benchmark_suite(
    path: Path | None = None,
) -> HybridLlamaBenchmarkSuite:
    source = path or _DEFAULT_SUITE
    try:
        return HybridLlamaBenchmarkSuite.model_validate_json(
            source.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, ValidationError) as exc:
        raise HybridLlamaBenchmarkError("El benchmark F.12 no es válido.") from exc


def hybrid_llama_benchmark_suite_sha256(path: Path | None = None) -> str:
    source = path or _DEFAULT_SUITE
    try:
        payload = source.read_bytes()
    except OSError as exc:
        raise HybridLlamaBenchmarkError("No fue posible leer el benchmark F.12.") from exc
    return hashlib.sha256(payload).hexdigest()


def _h1_quality(result: HybridLlamaRuntimeResult) -> float:
    h1_result = result.orchestration.llama_fiscal_hypothesis_h1
    if h1_result is None or not h1_result.generation_performed or h1_result.hypothesis is None:
        return 0.0
    h1 = h1_result.hypothesis
    return float(
        bool(h1.legal_problem.strip())
        and bool(h1.proposition.strip())
        and h1.requires_validation
        and h1.normative_validation_pending
        and not h1.changes_deterministic_result
        and not h1.can_control_legal_decision
        and not h1.asserts_external_legal_authority
    )


def _normative_grounding(result: HybridLlamaRuntimeResult) -> float:
    orchestration = result.orchestration
    h1_result = orchestration.llama_fiscal_hypothesis_h1
    initial = orchestration.llama_initial_context
    if h1_result is None or h1_result.hypothesis is None or initial is None:
        return 0.0
    allowed_h1 = set(initial.heuristic_route.exact_normative_hints)
    proposed_h1 = set(h1_result.hypothesis.candidate_normative_refs)
    if not proposed_h1.issubset(allowed_h1):
        return 0.0

    contexts = {
        item.document_id: item for item in orchestration.llama_jurisprudence_ratio_contexts
    }
    for h2_result in orchestration.llama_jurisprudential_ratio_h2:
        if not h2_result.generation_performed or h2_result.ratio is None:
            return 0.0
        context = contexts.get(h2_result.ratio.document_id)
        if context is None:
            return 0.0
        if not set(h2_result.ratio.interpreted_norms).issubset(
            set(context.candidate_normative_refs)
        ):
            return 0.0

    projection = result.decision.hybrid_projection
    return float(
        projection.legal_authority_source in {None, "normative_evidence"}
        and projection.normative_basis_preserved
        and not result.decision.legal_authority_reassigned_by_llm
    )


def _ratio_fidelity(
    result: HybridLlamaRuntimeResult,
    scenario: HybridLlamaBenchmarkScenario,
) -> float:
    if not scenario.expect_h2:
        return float(not result.h2_generation_attempted)
    h2_results = result.orchestration.llama_jurisprudential_ratio_h2
    contexts = {
        item.document_id: item for item in result.orchestration.llama_jurisprudence_ratio_contexts
    }
    if not h2_results:
        return 0.0
    for item in h2_results:
        if not item.generation_performed or item.ratio is None:
            return 0.0
        ratio = item.ratio
        context = contexts.get(ratio.document_id)
        if context is None or ratio.ratio_source_section.value != "justification":
            return 0.0
        normalized_justification = " ".join(context.justification_text.split())
        for span in ratio.supporting_spans:
            if span.page not in context.justification_source_pages:
                return 0.0
            if " ".join(span.text.split()) not in normalized_justification:
                return 0.0
    return 1.0


def _obiter_separation(
    result: HybridLlamaRuntimeResult,
    scenario: HybridLlamaBenchmarkScenario,
) -> float:
    if not scenario.expect_h2:
        return 1.0
    h2_results = result.orchestration.llama_jurisprudential_ratio_h2
    if not h2_results:
        return 0.0
    for item in h2_results:
        if item.ratio is None:
            return 0.0
        ratio = item.ratio
        obiter = {value.strip().casefold() for value in ratio.possible_obiter}
        essentials = {value.strip().casefold() for value in ratio.essential_premises}
        if obiter & essentials:
            return 0.0
        if ratio.proposed_ratio.strip().casefold() in obiter:
            return 0.0
    return 1.0


def _rbs_consistency(result: HybridLlamaRuntimeResult) -> float:
    contrast = result.orchestration.rbs_h1_contrast
    coordination = result.orchestration.hybrid_legal_coordination
    if contrast is None or coordination is None:
        return 0.0
    return float(
        contrast.rbs_authority_preserved
        and contrast.deterministic_result_preserved
        and not contrast.hypothesis_changes_rbs_result
        and not contrast.can_control_legal_decision
        and coordination.reasoning_controller == "rbs"
        and not coordination.majority_vote_used
        and not coordination.weighted_score_aggregation_used
    )


def _cbr_consistency(result: HybridLlamaRuntimeResult) -> float:
    contrast = result.orchestration.cbr_h1_contrast
    coordination = result.orchestration.hybrid_legal_coordination
    if contrast is None or coordination is None:
        return 0.0
    return float(
        contrast.cbr_is_experiential_support
        and not contrast.cbr_is_normative_authority
        and not contrast.cbr_is_jurisprudence
        and not contrast.cbr_votes_against_rbs
        and not contrast.hypothesis_changes_cbr_result
        and not contrast.can_control_legal_decision
        and not coordination.cbr_can_override_rbs
    )


def _jurisprudence_compliance(result: HybridLlamaRuntimeResult) -> float:
    coordination = result.orchestration.hybrid_legal_coordination
    projection = result.decision.hybrid_projection
    if coordination is None:
        return 0.0
    expected_binding = (
        coordination.jurisprudence_effect
        is JurisprudenceDecisionEffect.GOVERNING_INTERPRETATION
    )
    return float(
        projection.binding_interpretation_required == expected_binding
        and projection.jurisprudence_effect == coordination.jurisprudence_effect
        and projection.normative_basis_preserved
        and not projection.jurisprudence_replaces_normative_basis
        and not projection.jurisprudence_creates_second_conclusion
    )


def _argument_consistency(result: HybridLlamaRuntimeResult) -> float:
    verification = result.orchestration.hybrid_legal_verification
    if verification is None:
        return 0.0
    semantic = verification.semantic_draft
    no_semantic_conflict = bool(
        semantic is not None
        and not semantic.contradiction_codes
        and not semantic.hallucination_signals
        and not semantic.changes_canonical_conclusion
        and not semantic.introduces_new_facts
        and not semantic.introduces_new_normative_refs
        and not semantic.introduces_external_jurisprudence
        and not semantic.can_control_legal_decision
    )
    return float(
        verification.state is HybridLegalVerificationState.VERIFIED
        and verification.rbs_priority_preserved
        and verification.cbr_experiential_role_preserved
        and verification.normative_basis_preserved
        and verification.single_conclusion_preserved
        and no_semantic_conflict
    )


def _human_review_precision(
    result: HybridLlamaRuntimeResult,
    scenario: HybridLlamaBenchmarkScenario,
) -> float:
    return float(result.decision.requires_human_review == scenario.expect_human_review)


def _legal_authority_integrity(result: HybridLlamaRuntimeResult) -> float:
    projection = result.decision.hybrid_projection
    if result.decision.conclusion is not None and result.decision.controlling_source != (
        "normative_evidence"
    ):
        return 0.0
    return float(
        projection.normative_basis_preserved
        and not projection.h1_h2_used_as_legal_authority
        and not projection.cbr_used_as_legal_authority
        and not result.decision.legal_authority_reassigned_by_llm
    )


def _single_decision_integrity(result: HybridLlamaRuntimeResult) -> float:
    projection = result.decision.hybrid_projection
    return float(
        projection.single_determination_preserved
        and not projection.second_conclusion_created
        and not projection.jurisprudence_creates_second_conclusion
        and not result.decision.creates_second_conclusion
        and not result.source_results_reexecuted
    )


def _hallucination_rate(result: HybridLlamaRuntimeResult) -> float:
    verification = result.orchestration.hybrid_legal_verification
    if verification is None or verification.semantic_draft is None:
        # Fallar o no completar una generación es un error operacional, no una
        # alucinación. ``generation_success`` ya mide ese fallo por separado.
        return 0.0
    return 1.0 if verification.semantic_draft.hallucination_signals else 0.0


def _case_metrics(
    result: HybridLlamaRuntimeResult,
    scenario: HybridLlamaBenchmarkScenario,
) -> dict[str, float]:
    return {
        "generation_success": float(result.status is HybridLlamaRuntimeStatus.COMPLETED),
        "hypothesis_quality": _h1_quality(result),
        "normative_grounding": _normative_grounding(result),
        "ratio_fidelity": _ratio_fidelity(result, scenario),
        "obiter_separation": _obiter_separation(result, scenario),
        "rbs_consistency": _rbs_consistency(result),
        "cbr_consistency": _cbr_consistency(result),
        "jurisprudence_compliance": _jurisprudence_compliance(result),
        "argument_consistency": _argument_consistency(result),
        "human_review_precision": _human_review_precision(result, scenario),
        "legal_authority_integrity": _legal_authority_integrity(result),
        "single_decision_integrity": _single_decision_integrity(result),
        "hallucination_rate": _hallucination_rate(result),
    }


def _case_failures(
    metrics: dict[str, float],
    thresholds: HybridLlamaBenchmarkThresholds,
) -> list[str]:
    failures: list[str] = []
    for name in _METRIC_NAMES:
        value = metrics[name]
        threshold = float(getattr(thresholds, name))
        if value < threshold:
            failures.append(f"{name}={value:.3f}<threshold={threshold:.3f}")
    hallucination_rate = metrics["hallucination_rate"]
    if hallucination_rate > thresholds.hallucination_rate_max:
        failures.append(
            "hallucination_rate="
            f"{hallucination_rate:.3f}>max={thresholds.hallucination_rate_max:.3f}"
        )
    return failures


def evaluate_hybrid_llama_case(
    *,
    scenario: HybridLlamaBenchmarkScenario,
    provider_kind: HybridLlamaBenchmarkProviderKind,
    result: HybridLlamaRuntimeResult,
    thresholds: HybridLlamaBenchmarkThresholds,
    duration_seconds: float,
) -> HybridLlamaBenchmarkCaseResult:
    metrics = _case_metrics(result, scenario)
    failures = _case_failures(metrics, thresholds)
    if result.decision.conclusion != scenario.expected_conclusion:
        failures.append(
            "expected_conclusion_mismatch:"
            f"expected={scenario.expected_conclusion!r};actual={result.decision.conclusion!r}"
        )
    h1 = result.orchestration.llama_fiscal_hypothesis_h1
    h2_results = result.orchestration.llama_jurisprudential_ratio_h2
    verification = result.orchestration.hybrid_legal_verification
    return HybridLlamaBenchmarkCaseResult(
        scenario_id=scenario.scenario_id,
        provider_kind=provider_kind,
        provider_name=result.provider_name,
        model_name=result.model_name,
        provider_is_test_double=result.provider_is_test_double,
        runtime_completed=result.status is HybridLlamaRuntimeStatus.COMPLETED,
        decision_status=result.decision.status.value,
        conclusion=result.decision.conclusion,
        requires_human_review=result.decision.requires_human_review,
        h1_generated=bool(h1 and h1.generation_performed and h1.hypothesis is not None),
        h2_expected=scenario.expect_h2,
        h2_generated=bool(
            h2_results
            and all(item.generation_performed and item.ratio is not None for item in h2_results)
        ),
        semantic_verification_performed=bool(
            verification is not None and verification.semantic_verification_performed
        ),
        llm_failure_codes=list(result.llm_failure_codes),
        metrics=metrics,
        failures=failures,
        passed=not failures,
        duration_seconds=duration_seconds,
    )


def _mean(values: Iterable[float]) -> float:
    items = list(values)
    if not items:
        raise HybridLlamaBenchmarkError("F.12 requiere al menos un valor para promediar.")
    return sum(items) / len(items)


def _provider_report(
    *,
    kind: HybridLlamaBenchmarkProviderKind,
    cases: list[HybridLlamaBenchmarkCaseResult],
) -> HybridLlamaBenchmarkProviderReport:
    aggregate = {
        name: _mean(item.metrics[name] for item in cases)
        for name in (*_METRIC_NAMES, "hallucination_rate")
    }
    return HybridLlamaBenchmarkProviderReport(
        provider_kind=kind,
        provider_name=cases[0].provider_name,
        model_name=cases[0].model_name,
        case_count=len(cases),
        passed_case_count=sum(item.passed for item in cases),
        aggregate_metrics=aggregate,
        overall_passed=all(item.passed for item in cases),
        cases=cases,
    )


def _run_provider(
    *,
    provider: F12BenchmarkProvider,
    provider_kind: HybridLlamaBenchmarkProviderKind,
    provider_is_test_double: bool,
    suite: HybridLlamaBenchmarkSuite,
) -> HybridLlamaBenchmarkProviderReport:
    runtime = build_f12_runtime(
        provider,
        provider_is_test_double=provider_is_test_double,
    )
    cases: list[HybridLlamaBenchmarkCaseResult] = []
    for scenario in suite.scenarios:
        request = build_f12_request(with_jurisprudence=scenario.with_jurisprudence)
        started = time.perf_counter()
        result = runtime.run(request)
        duration = time.perf_counter() - started
        cases.append(
            evaluate_hybrid_llama_case(
                scenario=scenario,
                provider_kind=provider_kind,
                result=result,
                thresholds=suite.thresholds,
                duration_seconds=duration,
            )
        )
    return _provider_report(kind=provider_kind, cases=cases)


def _comparison(
    reference: HybridLlamaBenchmarkProviderReport,
    real: HybridLlamaBenchmarkProviderReport,
) -> tuple[list[HybridLlamaBenchmarkComparisonCase], float]:
    reference_by_id = {item.scenario_id: item for item in reference.cases}
    comparisons: list[HybridLlamaBenchmarkComparisonCase] = []
    for real_case in real.cases:
        reference_case = reference_by_id[real_case.scenario_id]
        same_status = reference_case.decision_status == real_case.decision_status
        same_conclusion = reference_case.conclusion == real_case.conclusion
        comparisons.append(
            HybridLlamaBenchmarkComparisonCase(
                scenario_id=real_case.scenario_id,
                same_decision_status=same_status,
                same_conclusion=same_conclusion,
                conclusion_stability=float(same_status and same_conclusion),
                reference_requires_human_review=reference_case.requires_human_review,
                real_requires_human_review=real_case.requires_human_review,
            )
        )
    stability = _mean(item.conclusion_stability for item in comparisons)
    return comparisons, stability


def run_hybrid_llama_benchmark(
    *,
    reference_provider: F12BenchmarkProvider,
    real_provider: F12BenchmarkProvider,
    suite: HybridLlamaBenchmarkSuite | None = None,
    suite_path: Path | None = None,
) -> HybridLlamaBenchmarkReport:
    active_suite = suite or load_hybrid_llama_benchmark_suite(suite_path)
    reference = _run_provider(
        provider=reference_provider,
        provider_kind=HybridLlamaBenchmarkProviderKind.REFERENCE,
        provider_is_test_double=True,
        suite=active_suite,
    )
    real = _run_provider(
        provider=real_provider,
        provider_kind=HybridLlamaBenchmarkProviderKind.REAL_LLAMA,
        provider_is_test_double=False,
        suite=active_suite,
    )
    comparisons, conclusion_stability = _comparison(reference, real)
    if real.provider_name != "llama-cpp-python":
        raise HybridLlamaBenchmarkError(
            "F.12 exige llama-cpp-python como proveedor real comparado."
        )
    if any(item.provider_is_test_double for item in real.cases):
        raise HybridLlamaBenchmarkError("F.12 rechazó un doble presentado como Llama real.")

    hallucination_rate = real.aggregate_metrics["hallucination_rate"]
    safety_metric_names = (
        "normative_grounding",
        "rbs_consistency",
        "cbr_consistency",
        "jurisprudence_compliance",
        "legal_authority_integrity",
        "single_decision_integrity",
    )
    safety_passed = all(
        real.aggregate_metrics[name] >= float(getattr(active_suite.thresholds, name))
        for name in safety_metric_names
    ) and hallucination_rate <= active_suite.thresholds.hallucination_rate_max

    quality_passed = (
        real.overall_passed
        and conclusion_stability >= active_suite.thresholds.conclusion_stability
    )
    return HybridLlamaBenchmarkReport(
        suite_id=active_suite.suite_id,
        suite_sha256=hybrid_llama_benchmark_suite_sha256(suite_path),
        reference=reference,
        real_llama=real,
        comparison_cases=comparisons,
        conclusion_stability=conclusion_stability,
        hallucination_rate=hallucination_rate,
        safety_passed=safety_passed,
        quality_passed=quality_passed,
        overall_passed=reference.overall_passed and safety_passed and quality_passed,
        limitations=[
            (
                "El suite F.12 es sintético y prueba fronteras arquitectónicas; "
                "no sustituye evaluación jurídica humana."
            ),
            "El benchmark real depende del GGUF, CPU y parámetros configurados en F.11.",
        ],
    )


def export_hybrid_llama_benchmark_report(
    report: HybridLlamaBenchmarkReport,
    path: Path,
) -> Path:
    if path.suffix.casefold() != ".json":
        raise HybridLlamaBenchmarkError("El reporte F.12 debe usar extensión .json.")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    try:
        temporary.write_text(
            json.dumps(
                report.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise HybridLlamaBenchmarkError("No fue posible escribir el reporte F.12.") from exc
    return path
