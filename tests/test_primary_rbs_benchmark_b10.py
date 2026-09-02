from pathlib import Path

from app.services.primary_rbs_benchmark import (
    load_primary_rbs_benchmark_suite,
    run_primary_rbs_benchmark,
    validate_primary_rbs_benchmark_suite,
)
from app.services.primary_rbs_corpus_validation import (
    load_primary_rbs_corpus_validation_report,
)
from app.services.primary_rbs_deduplication import (
    load_primary_rbs_deduplication_map,
)
from app.services.primary_rbs_existing_integration import (
    load_existing_rbs_rule_integration_map,
)
from app.services.primary_rbs_inventory import load_current_rbs_inventory

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "app" / "resources"
PRODUCTION = ROOT / "rules" / "production"


def _load_inputs():
    suite = load_primary_rbs_benchmark_suite(
        RESOURCES / "primary_rbs_benchmark_suite.json"
    )
    integration = load_existing_rbs_rule_integration_map(
        RESOURCES / "primary_rbs_existing_integration.json"
    )
    inventory = load_current_rbs_inventory(
        RESOURCES / "current_rbs_inventory.json"
    )
    deduplication = load_primary_rbs_deduplication_map(
        RESOURCES / "primary_rbs_deduplication_map.json"
    )
    corpus_validation = load_primary_rbs_corpus_validation_report(
        RESOURCES / "primary_rbs_corpus_validation.json"
    )
    return (
        suite,
        integration,
        inventory,
        deduplication,
        corpus_validation,
    )


def _run_benchmark():
    (
        suite,
        integration,
        inventory,
        deduplication,
        corpus_validation,
    ) = _load_inputs()
    return run_primary_rbs_benchmark(
        production_dir=PRODUCTION,
        suite=suite,
        integration_map=integration,
        inventory=inventory,
        deduplication=deduplication,
        corpus_validation=corpus_validation,
    )


def test_b10_suite_covers_exactly_the_14_integrated_rules() -> None:
    (
        suite,
        integration,
        inventory,
        deduplication,
        corpus_validation,
    ) = _load_inputs()

    validate_primary_rbs_benchmark_suite(
        suite,
        integration,
        inventory,
        deduplication,
        corpus_validation,
    )

    assert suite.expected_case_count == 10
    assert len(suite.required_rule_coverage) == 14
    assert set(suite.required_rule_coverage) == {
        item.rule_id for item in integration.integrations
    }


def test_b10_benchmark_passes_all_explicit_cases() -> None:
    report = _run_benchmark()

    assert report.total_cases == 10
    assert report.passed_cases == 10
    assert report.pass_rate == 1.0
    assert report.rule_coverage_rate == 1.0
    assert report.missing_required_rule_coverage == []
    assert report.threshold_met is True
    assert report.all_passed is True


def test_b10_fail_closed_case_produces_no_rule_or_derivation() -> None:
    report = _run_benchmark()
    result = next(
        item for item in report.results if item.case_id == "B10-CASE-001"
    )

    assert result.passed is True
    assert result.matched_rule_ids == []
    assert result.derivation_count == 0
    assert result.unauthorized_normative_refs == []


def test_b10_professional_chain_preserves_derivation_traceability() -> None:
    report = _run_benchmark()
    result = next(
        item for item in report.results if item.case_id == "B10-CASE-008"
    )

    assert result.passed is True
    assert result.derivation_count == 6
    assert result.missing_derivation_edges == []
    assert result.unauthorized_normative_refs == []


def test_b10_scope_and_closed_evidence_contract_are_explicit() -> None:
    suite, _, _, _, _ = _load_inputs()
    report = _run_benchmark()

    assert suite.validates_current_dataset_only is True
    assert suite.claims_full_mexican_tax_law_coverage is False
    assert suite.uses_existing_rule_engine_only is True
    assert suite.allows_external_legal_evidence is False
    assert report.validates_current_dataset_only is True
    assert report.claims_full_mexican_tax_law_coverage is False
    assert all(
        result.unauthorized_normative_refs == []
        for result in report.results
    )
