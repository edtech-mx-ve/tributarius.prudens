from pathlib import Path

from app.services.primary_rbs_corpus_validation import (
    load_primary_rbs_corpus_validation_report,
    validate_primary_rbs_against_current_corpus,
)
from app.services.primary_rbs_decision_boundary import (
    load_primary_rbs_decision_boundary_map,
)
from app.services.primary_rbs_inventory import load_current_rbs_inventory

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "app" / "resources" / "primary_rbs_corpus_validation.json"
BOUNDARY_PATH = ROOT / "app" / "resources" / "primary_rbs_decision_boundary.json"
INVENTORY_PATH = ROOT / "app" / "resources" / "current_rbs_inventory.json"
MANIFEST_PATH = ROOT / "app" / "resources" / "primary_legal_knowledge_manifest.json"
CATALOG_PATH = ROOT / "app" / "resources" / "fiscal_corpus_15_catalog.json"
TEMPORAL_PATH = ROOT / "knowledge" / "temporal" / "temporal_provenance_registry.json"


def test_b8_validates_relations_and_existing_rules_against_internal_corpus() -> None:
    report = load_primary_rbs_corpus_validation_report(REPORT_PATH)
    boundaries = load_primary_rbs_decision_boundary_map(BOUNDARY_PATH)
    inventory = load_current_rbs_inventory(INVENTORY_PATH)

    validate_primary_rbs_against_current_corpus(
        report,
        boundaries,
        inventory,
        primary_manifest_path=MANIFEST_PATH,
        fiscal_catalog_path=CATALOG_PATH,
        temporal_registry_path=TEMPORAL_PATH,
    )

    assert len(report.relation_validations) == 18
    assert len(report.existing_rule_validations) == 14
    assert len(report.normative_corpus_ids) == 12


def test_b8_preserves_temporal_fail_closed_contract() -> None:
    report = load_primary_rbs_corpus_validation_report(REPORT_PATH)

    assert report.temporal_policy_fail_closed is True
    assert set(report.document_wide_temporal_blocks) == {"cpeum", "liva"}
    assert all(
        not validation.temporal_applicability_confirmed
        for validation in report.relation_validations
    )
    assert all(
        validation.requires_case_date_validation
        for validation in report.relation_validations
    )
    assert all(
        not validation.determination_ready
        for validation in report.relation_validations
    )


def test_b8_propagates_document_wide_temporal_blocks() -> None:
    report = load_primary_rbs_corpus_validation_report(REPORT_PATH)
    blocked = set(report.document_wide_temporal_blocks)

    for validation in report.relation_validations:
        assert set(validation.blocked_normative_sources) == (
            set(validation.normative_source_ids) & blocked
        )


def test_b8_exact_refs_are_known_from_existing_rules_only() -> None:
    report = load_primary_rbs_corpus_validation_report(REPORT_PATH)
    inventory = load_current_rbs_inventory(INVENTORY_PATH)
    known_refs = {ref for rule in inventory.rules for ref in rule.normative_refs}
    primary_exact_refs = {
        ref
        for validation in report.relation_validations
        for ref in validation.exact_normative_refs
    }

    assert primary_exact_refs <= known_refs
    assert primary_exact_refs == {
        "cff:articulo_1",
        "cff:articulo_2",
        "lfdc:articulo_2",
        "lisr:articulo_94",
        "lisr:articulo_100",
        "lisr:articulo_110",
    }


def test_b8_validates_all_existing_rule_refs_without_changing_execution() -> None:
    report = load_primary_rbs_corpus_validation_report(REPORT_PATH)
    all_existing_refs = {
        ref
        for validation in report.existing_rule_validations
        for ref in validation.normative_refs
    }

    assert all_existing_refs == {
        "cff:articulo_1",
        "cff:articulo_2",
        "lfdc:articulo_2",
        "lisr:articulo_94",
        "lisr:articulo_100",
        "lisr:articulo_110",
        "lisr:articulo_114",
    }
    assert report.modifies_production_rules is False
    assert all(
        validation.execution_contract_unchanged
        for validation in report.existing_rule_validations
    )
