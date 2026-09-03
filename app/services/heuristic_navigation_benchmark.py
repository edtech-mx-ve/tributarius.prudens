from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.domain.heuristic_navigation_benchmark import (
    HeuristicNavigationBenchmarkCase,
    HeuristicNavigationBenchmarkCaseResult,
    HeuristicNavigationBenchmarkDimension,
    HeuristicNavigationBenchmarkReport,
    HeuristicNavigationBenchmarkSuite,
)
from app.domain.query import QueryAnalysis, QueryDimensionName
from app.services.normative_ranking import load_default_normative_corpus_ids
from app.services.temporal_control import resolve_temporal_query_context
from llm.providers.runtime_query import RuntimeQueryAnalyzerProvider
from llm.query_analyzer import QueryAnalyzer


class HeuristicNavigationBenchmarkError(RuntimeError):
    """Error controlado del benchmark D.10."""


def load_heuristic_navigation_benchmark_suite(
    path: Path,
) -> HeuristicNavigationBenchmarkSuite:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise HeuristicNavigationBenchmarkError(
            f"No existe el benchmark heurístico D.10: {resolved}"
        )
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        return HeuristicNavigationBenchmarkSuite.model_validate(payload)
    except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as exc:
        raise HeuristicNavigationBenchmarkError(
            "El benchmark heurístico D.10 no es válido."
        ) from exc


def validate_heuristic_navigation_benchmark_suite(
    suite: HeuristicNavigationBenchmarkSuite,
) -> None:
    corpus_ids = list(load_default_normative_corpus_ids())
    if len(corpus_ids) != suite.expected_normative_corpus_count:
        raise HeuristicNavigationBenchmarkError(
            "D.10 no coincide con los 12 corpus normativos A.8 actuales."
        )
    if len(set(corpus_ids)) != suite.expected_normative_corpus_count:
        raise HeuristicNavigationBenchmarkError("D.10 detectó corpus A.8 duplicados.")
    covered = {
        dimension
        for case in suite.cases
        for dimension in case.dimensions
    }
    if covered != set(suite.required_dimensions):
        raise HeuristicNavigationBenchmarkError(
            "Los casos D.10 no cubren las nueve capas declaradas D.1-D.9."
        )


def _dimension_values(analysis: QueryAnalysis) -> dict[QueryDimensionName, list[str]]:
    multidimensional = analysis.multidimensional
    if multidimensional is None:
        return {}
    result: dict[QueryDimensionName, list[str]] = {}
    for item in multidimensional.dimensions:
        result.setdefault(item.dimension, []).append(item.value)
    return result


def _append_mismatch(
    diagnostics: list[str],
    label: str,
    expected: object,
    observed: object,
) -> None:
    if expected != observed:
        diagnostics.append(f"{label}: esperado={expected!r}; observado={observed!r}")


def _boundary_preserved(analysis: QueryAnalysis) -> bool:
    layers = (
        analysis.multidimensional,
        analysis.primary_source_activation,
        analysis.rbs_orientation,
        analysis.cbr_orientation,
        analysis.normative_ranking,
        analysis.structural_navigation,
        analysis.focused_rag_plan,
        analysis.full_corpus_expansion_plan,
        analysis.temporal_control_plan,
    )
    return all(
        layer is not None and layer.can_control_legal_decision is False
        for layer in layers
    )


def _full_corpus_preserved(analysis: QueryAnalysis, corpus_ids: list[str]) -> bool:
    layers = (
        analysis.primary_source_activation,
        analysis.rbs_orientation,
        analysis.cbr_orientation,
        analysis.normative_ranking,
        analysis.structural_navigation,
        analysis.focused_rag_plan,
        analysis.full_corpus_expansion_plan,
        analysis.temporal_control_plan,
    )
    return all(
        layer is not None and layer.normative_corpus_ids == corpus_ids
        for layer in layers
    )


def _evaluate_case(
    case: HeuristicNavigationBenchmarkCase,
    analyzer: QueryAnalyzer,
    corpus_ids: list[str],
) -> HeuristicNavigationBenchmarkCaseResult:
    analysis = analyzer.analyze(case.query)
    diagnostics: list[str] = []

    layers = (
        analysis.multidimensional,
        analysis.primary_source_activation,
        analysis.rbs_orientation,
        analysis.cbr_orientation,
        analysis.normative_ranking,
        analysis.structural_navigation,
        analysis.focused_rag_plan,
        analysis.full_corpus_expansion_plan,
        analysis.temporal_control_plan,
    )
    if any(layer is None for layer in layers):
        raise HeuristicNavigationBenchmarkError(
            f"{case.case_id} no produjo la cadena completa D.1-D.9."
        )

    multidimensional = analysis.multidimensional
    primary = analysis.primary_source_activation
    rbs = analysis.rbs_orientation
    cbr = analysis.cbr_orientation
    ranking = analysis.normative_ranking
    navigation = analysis.structural_navigation
    focused = analysis.focused_rag_plan
    expansion = analysis.full_corpus_expansion_plan
    temporal = analysis.temporal_control_plan
    assert multidimensional is not None
    assert primary is not None
    assert rbs is not None
    assert cbr is not None
    assert ranking is not None
    assert navigation is not None
    assert focused is not None
    assert expansion is not None
    assert temporal is not None

    _append_mismatch(
        diagnostics,
        "primary_intent",
        case.expected_primary_intent,
        analysis.primary_intent,
    )
    observed_dimensions = _dimension_values(analysis)
    for dimension, expected_values in case.expected_dimension_values.items():
        _append_mismatch(
            diagnostics,
            f"dimension:{dimension.value}",
            expected_values,
            observed_dimensions.get(dimension, []),
        )

    if case.expect_problem_absent:
        _append_mismatch(diagnostics, "problem_id", None, multidimensional.primary_problem_id)
    elif case.expected_problem_id is not None:
        _append_mismatch(
            diagnostics,
            "problem_id",
            case.expected_problem_id,
            multidimensional.primary_problem_id,
        )

    if case.expect_institution_absent:
        _append_mismatch(
            diagnostics,
            "institution_id",
            None,
            multidimensional.primary_institution_id,
        )
    elif case.expected_institution_id is not None:
        _append_mismatch(
            diagnostics,
            "institution_id",
            case.expected_institution_id,
            multidimensional.primary_institution_id,
        )

    primary_ids = [item.entry_id for item in primary.entries]
    missing_primary = sorted(set(case.required_primary_entry_ids) - set(primary_ids))
    forbidden_primary = sorted(set(case.forbidden_primary_entry_ids) & set(primary_ids))
    if missing_primary:
        diagnostics.append(f"primary_missing:{missing_primary}")
    if forbidden_primary:
        diagnostics.append(f"primary_forbidden_active:{forbidden_primary}")

    rbs_ids = [item.relation_id for item in rbs.relations]
    missing_rbs = sorted(set(case.required_rbs_relation_ids) - set(rbs_ids))
    if missing_rbs:
        diagnostics.append(f"rbs_missing:{missing_rbs}")

    if case.expect_cbr_family_absent:
        _append_mismatch(diagnostics, "cbr_family", None, cbr.query_primary_family_id)
    elif case.expected_cbr_primary_family_id is not None:
        _append_mismatch(
            diagnostics,
            "cbr_family",
            case.expected_cbr_primary_family_id,
            cbr.query_primary_family_id,
        )
    if cbr.returned_count < case.minimum_cbr_match_count:
        diagnostics.append(
            "cbr_match_count: "
            f"mínimo={case.minimum_cbr_match_count}; observado={cbr.returned_count}"
        )
    cbr_ids = [item.situation_id for item in cbr.matches]
    missing_cbr = sorted(set(case.required_cbr_situation_ids) - set(cbr_ids))
    forbidden_cbr = sorted(set(case.forbidden_cbr_situation_ids) & set(cbr_ids))
    if missing_cbr:
        diagnostics.append(f"cbr_missing:{missing_cbr}")
    if forbidden_cbr:
        diagnostics.append(f"cbr_forbidden_active:{forbidden_cbr}")

    _append_mismatch(
        diagnostics,
        "focus_source_ids",
        case.expected_focus_source_ids,
        ranking.focus_source_ids,
    )
    _append_mismatch(
        diagnostics,
        "navigation_focus_source_ids",
        case.expected_focus_source_ids,
        navigation.focus_source_ids,
    )
    _append_mismatch(
        diagnostics,
        "rag_focus_source_ids",
        case.expected_focus_source_ids,
        focused.focus_source_ids,
    )
    missing_refs = sorted(
        set(case.required_exact_normative_refs) - set(focused.exact_normative_refs)
    )
    if missing_refs:
        diagnostics.append(f"exact_refs_missing:{missing_refs}")
    _append_mismatch(
        diagnostics,
        "focused_rag_plan_applied",
        case.expected_rag_plan_applied,
        focused.plan_applied,
    )
    _append_mismatch(
        diagnostics,
        "expansion_source_count",
        case.expected_expansion_source_count,
        len(expansion.expansion_source_ids),
    )
    combined_sources = list(
        dict.fromkeys([*focused.focus_source_ids, *expansion.expansion_source_ids])
    )
    if set(combined_sources) != set(corpus_ids):
        diagnostics.append(
            "full_corpus_union: "
            f"esperado={sorted(corpus_ids)!r}; observado={sorted(combined_sources)!r}"
        )

    _append_mismatch(
        diagnostics,
        "explicit_query_years",
        case.expected_explicit_query_years,
        temporal.explicit_query_years,
    )
    _append_mismatch(
        diagnostics,
        "historical_context",
        case.expected_historical_context,
        temporal.historical_context,
    )
    missing_temporal_blocks = sorted(
        set(case.required_temporal_blocked_source_ids)
        - set(temporal.temporal_blocked_source_ids)
    )
    if missing_temporal_blocks:
        diagnostics.append(f"temporal_blocks_missing:{missing_temporal_blocks}")

    resolution = resolve_temporal_query_context(temporal, None)
    _append_mismatch(
        diagnostics,
        "year_resolution",
        case.expected_year_resolution,
        resolution.resolution,
    )
    _append_mismatch(
        diagnostics,
        "resolved_fiscal_year",
        case.expected_resolved_fiscal_year,
        resolution.resolved_fiscal_year,
    )

    full_corpus_preserved = _full_corpus_preserved(analysis, corpus_ids)
    if not full_corpus_preserved:
        diagnostics.append("full_corpus_contract_failed")
    boundary_preserved = _boundary_preserved(analysis)
    if not boundary_preserved:
        diagnostics.append("legal_decision_boundary_failed")

    return HeuristicNavigationBenchmarkCaseResult(
        case_id=case.case_id,
        passed=not diagnostics,
        resico_case=case.resico_case,
        diagnostics=diagnostics,
        observed_focus_source_ids=list(ranking.focus_source_ids),
        observed_primary_entry_ids=primary_ids,
        observed_rbs_relation_ids=rbs_ids,
        observed_cbr_situation_ids=cbr_ids,
        observed_explicit_query_years=list(temporal.explicit_query_years),
        observed_year_resolution=resolution.resolution,
        observed_resolved_fiscal_year=resolution.resolved_fiscal_year,
        full_corpus_preserved=full_corpus_preserved,
        legal_decision_boundary_preserved=boundary_preserved,
    )


def run_heuristic_navigation_benchmark(
    suite: HeuristicNavigationBenchmarkSuite,
) -> HeuristicNavigationBenchmarkReport:
    """Ejecuta D.10 sobre el QueryAnalyzer real y las capas D.1-D.9."""
    validate_heuristic_navigation_benchmark_suite(suite)
    analyzer = QueryAnalyzer(RuntimeQueryAnalyzerProvider())
    corpus_ids = list(load_default_normative_corpus_ids())
    results = [
        _evaluate_case(case, analyzer, corpus_ids)
        for case in suite.cases
    ]
    passed_cases = sum(result.passed for result in results)
    pass_rate = passed_cases / len(results)
    resico_results = [result for result in results if result.resico_case]
    passed_resico_cases = sum(result.passed for result in resico_results)
    covered_dimensions = sorted(
        {
            dimension
            for case in suite.cases
            for dimension in case.dimensions
        },
        key=lambda item: list(HeuristicNavigationBenchmarkDimension).index(item),
    )
    missing_required_dimensions = [
        item for item in suite.required_dimensions if item not in covered_dimensions
    ]
    full_corpus_contract_passed = all(result.full_corpus_preserved for result in results)
    legal_decision_boundary_passed = all(
        result.legal_decision_boundary_preserved for result in results
    )
    threshold_met = pass_rate >= suite.pass_threshold
    all_passed = (
        passed_cases == len(results)
        and passed_resico_cases == suite.expected_resico_case_count
        and not missing_required_dimensions
        and full_corpus_contract_passed
        and legal_decision_boundary_passed
        and threshold_met
    )
    return HeuristicNavigationBenchmarkReport(
        schema_version="1.0",
        benchmark_version=suite.benchmark_version,
        total_cases=len(results),
        passed_cases=passed_cases,
        pass_rate=pass_rate,
        resico_cases=len(resico_results),
        passed_resico_cases=passed_resico_cases,
        covered_dimensions=covered_dimensions,
        missing_required_dimensions=missing_required_dimensions,
        full_corpus_contract_passed=full_corpus_contract_passed,
        legal_decision_boundary_passed=legal_decision_boundary_passed,
        results=results,
        threshold_met=threshold_met,
        all_passed=all_passed,
        validates_current_dataset_only=suite.validates_current_dataset_only,
        claims_full_mexican_tax_law_coverage=suite.claims_full_mexican_tax_law_coverage,
    )
