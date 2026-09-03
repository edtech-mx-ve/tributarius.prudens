from __future__ import annotations

from pathlib import Path

from app.domain.primary_cbr_benchmark import PrimaryCBRBenchmarkDimension
from app.domain.primary_cbr_legal_similarity import PrimaryCBRLegalSimilarityDecision
from app.services.primary_cbr_benchmark import (
    load_primary_cbr_benchmark_suite,
    run_primary_cbr_benchmark,
    validate_primary_cbr_benchmark_suite,
)
from app.services.primary_cbr_corpus_validation import (
    load_primary_cbr_corpus_validation_report,
)
from app.services.primary_cbr_families import load_primary_cbr_family_registry
from app.services.primary_cbr_legal_similarity import (
    load_primary_cbr_legal_similarity_index,
)
from app.services.primary_cbr_levels import load_primary_cbr_level_registry
from app.services.primary_cbr_problem_institution import (
    load_primary_cbr_problem_institution_classification,
)

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "app" / "resources"


def _inputs():
    suite = load_primary_cbr_benchmark_suite(
        RESOURCES / "primary_cbr_benchmark_suite.json"
    )
    classification = load_primary_cbr_problem_institution_classification(
        RESOURCES / "primary_cbr_problem_institution.json"
    )
    corpus = load_primary_cbr_corpus_validation_report(
        RESOURCES / "primary_cbr_corpus_validation.json"
    )
    families = load_primary_cbr_family_registry(RESOURCES / "primary_cbr_families.json")
    similarity = load_primary_cbr_legal_similarity_index(
        RESOURCES / "primary_cbr_legal_similarity.json"
    )
    levels = load_primary_cbr_level_registry(RESOURCES / "primary_cbr_levels.json")
    return suite, classification, corpus, families, similarity, levels


def test_c11_benchmark_runs_ten_cases_at_perfect_threshold() -> None:
    report = run_primary_cbr_benchmark(*_inputs())

    assert report.total_cases == 10
    assert report.passed_cases == 10
    assert report.pass_rate == 1.0
    assert report.threshold_met
    assert report.all_passed
    assert all(result.passed for result in report.results)


def test_c11_covers_all_six_declared_dimensions() -> None:
    suite, *rest = _inputs()
    report = run_primary_cbr_benchmark(suite, *rest)

    assert set(report.covered_dimensions) == set(PrimaryCBRBenchmarkDimension)
    assert report.missing_required_dimensions == []
    assert report.global_contract_passed
    assert set(suite.required_dimensions) == set(PrimaryCBRBenchmarkDimension)


def test_c11_exercises_all_five_similarity_decisions() -> None:
    report = run_primary_cbr_benchmark(*_inputs())
    observed = {
        result.observed_similarity_decision
        for result in report.results
        if result.observed_similarity_decision is not None
    }

    assert observed == set(PrimaryCBRLegalSimilarityDecision)
    eligible = next(result for result in report.results if result.case_id == "C11-CASE-006")
    assert eligible.observed_similarity == 1.0
    assert eligible.observed_conflict_fields == []


def test_c11_keeps_historical_and_normative_failures_fail_closed() -> None:
    report = run_primary_cbr_benchmark(*_inputs())
    by_id = {result.case_id: result for result in report.results}

    assert by_id["C11-CASE-003"].passed
    assert by_id["C11-CASE-004"].passed
    assert by_id["C11-CASE-005"].passed
    assert by_id["C11-CASE-009"].observed_similarity_decision is (
        PrimaryCBRLegalSimilarityDecision.BLOCKED_HISTORICAL_CONTEXT
    )


def test_c11_freezes_global_c9_c10_dataset_contract() -> None:
    suite, _, _, _, similarity, levels = _inputs()

    assert suite.expected_source_situation_count == 37
    assert suite.expected_validated_membership_count == 20
    assert suite.expected_operational_membership_count == 0
    assert similarity.profile_count == 37
    assert similarity.total_pair_count == 666
    assert similarity.eligible_pair_count == 136
    assert levels.primary_membership_count == 37
    assert levels.validated_membership_count == 20
    assert levels.operational_membership_count == 0


def test_c11_suite_is_reproducible_and_does_not_claim_full_law_coverage() -> None:
    suite, classification, corpus, families, similarity, levels = _inputs()

    validate_primary_cbr_benchmark_suite(
        suite,
        classification,
        corpus,
        families,
        similarity,
        levels,
    )
    first = run_primary_cbr_benchmark(
        suite,
        classification,
        corpus,
        families,
        similarity,
        levels,
    )
    second = run_primary_cbr_benchmark(
        suite,
        classification,
        corpus,
        families,
        similarity,
        levels,
    )

    assert first == second
    assert first.validates_current_dataset_only
    assert not first.claims_full_mexican_tax_law_coverage
    assert not suite.allows_external_legal_evidence
    assert not suite.creates_operational_cases
