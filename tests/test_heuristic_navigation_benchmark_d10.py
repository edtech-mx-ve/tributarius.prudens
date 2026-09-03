from __future__ import annotations

from pathlib import Path

from app.domain.heuristic_navigation_benchmark import (
    HeuristicNavigationBenchmarkDimension,
    HeuristicNavigationBenchmarkReport,
    HeuristicNavigationBenchmarkSuite,
)
from app.domain.query import TemporalYearResolution
from app.services.heuristic_navigation_benchmark import (
    load_heuristic_navigation_benchmark_suite,
    run_heuristic_navigation_benchmark,
    validate_heuristic_navigation_benchmark_suite,
)

ROOT = Path(__file__).resolve().parents[1]
SUITE_PATH = ROOT / "app" / "resources" / "heuristic_navigation_benchmark_suite.json"


def _suite() -> HeuristicNavigationBenchmarkSuite:
    return load_heuristic_navigation_benchmark_suite(SUITE_PATH)


def _report() -> HeuristicNavigationBenchmarkReport:
    return run_heuristic_navigation_benchmark(_suite())


def test_d10_runs_ten_cases_at_perfect_threshold() -> None:
    report = _report()

    assert report.total_cases == 10
    assert report.passed_cases == 10
    assert report.pass_rate == 1.0
    assert report.threshold_met is True
    assert report.all_passed is True
    assert all(result.passed for result in report.results)


def test_d10_resico_cases_pass_without_reactivating_rif_history() -> None:
    report = _report()
    resico = [item for item in report.results if item.resico_case]

    assert report.resico_cases == 2
    assert report.passed_resico_cases == 2
    assert len(resico) == 2
    assert all("PRODECON-12" not in item.observed_primary_entry_ids for item in resico)
    historical_ids = {"P-CBR-SIT-023", "P-CBR-SIT-024", "U-CBR-SIT-008"}
    assert all(not historical_ids.intersection(item.observed_cbr_situation_ids) for item in resico)
    assert all(item.observed_resolved_fiscal_year == 2026 for item in resico)


def test_d10_rif_case_remains_historical_and_temporally_explicit() -> None:
    report = _report()
    rif = next(item for item in report.results if item.case_id == "D10-CASE-005")

    assert rif.passed is True
    assert "PRODECON-12" in rif.observed_primary_entry_ids
    assert {"P-CBR-SIT-023", "P-CBR-SIT-024", "U-CBR-SIT-008"}.issubset(
        rif.observed_cbr_situation_ids
    )
    assert rif.observed_explicit_query_years == [2020]
    assert rif.observed_year_resolution is TemporalYearResolution.QUERY_EXPLICIT_YEAR
    assert rif.observed_resolved_fiscal_year == 2020


def test_d10_unknown_query_fails_closed_and_expands_without_inventing_focus() -> None:
    report = _report()
    unknown = next(item for item in report.results if item.case_id == "D10-CASE-010")

    assert unknown.passed is True
    assert unknown.observed_focus_source_ids == []
    assert unknown.observed_primary_entry_ids == []
    assert unknown.observed_rbs_relation_ids == []
    assert unknown.observed_cbr_situation_ids == []
    assert unknown.observed_year_resolution is TemporalYearResolution.QUERY_DATE_ONLY
    assert unknown.observed_resolved_fiscal_year is None
    assert unknown.full_corpus_preserved is True


def test_d10_covers_all_nine_layers_and_preserves_global_boundaries() -> None:
    suite = _suite()
    validate_heuristic_navigation_benchmark_suite(suite)
    report = run_heuristic_navigation_benchmark(suite)

    assert set(report.covered_dimensions) == set(HeuristicNavigationBenchmarkDimension)
    assert report.missing_required_dimensions == []
    assert report.full_corpus_contract_passed is True
    assert report.legal_decision_boundary_passed is True
    assert all(item.full_corpus_preserved for item in report.results)
    assert all(item.legal_decision_boundary_preserved for item in report.results)


def test_d10_is_reproducible_and_scoped_to_current_dataset() -> None:
    suite = _suite()
    first = run_heuristic_navigation_benchmark(suite)
    second = run_heuristic_navigation_benchmark(suite)

    assert first == second
    assert suite.baseline_commit == "d0158cdcf79506ba63763a585b4887ae8e5ebf97"
    assert suite.validates_current_dataset_only is True
    assert suite.claims_full_mexican_tax_law_coverage is False
    assert suite.preserves_full_normative_corpus is True
    assert suite.allows_external_legal_evidence is False
    assert suite.can_control_legal_decision is False
    assert first.validates_current_dataset_only is True
    assert first.claims_full_mexican_tax_law_coverage is False
