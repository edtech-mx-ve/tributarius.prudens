from pathlib import Path

from app.services.primary_rbs_corpus_validation import (
    load_primary_rbs_corpus_validation_report,
)
from app.services.primary_rbs_deduplication import (
    load_primary_rbs_deduplication_map,
)
from app.services.primary_rbs_existing_integration import (
    infer_integrated_existing_rule_facts,
    load_existing_rbs_rule_integration_map,
    load_integrated_existing_rule_set,
    validate_existing_rbs_rule_integration,
)
from app.services.primary_rbs_inventory import load_current_rbs_inventory

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "app" / "resources"
PRODUCTION = ROOT / "rules" / "production"


def _load_inputs():
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
    return integration, inventory, deduplication, corpus_validation


def test_b9_integrates_exactly_the_14_existing_rules() -> None:
    integration, inventory, deduplication, corpus_validation = _load_inputs()

    validate_existing_rbs_rule_integration(
        integration,
        inventory,
        deduplication,
        corpus_validation,
    )

    assert integration.total_rules == 14
    assert {
        (item.rule_id, item.version) for item in integration.integrations
    } == {
        (item.rule_id, item.version) for item in inventory.rules
    }


def test_b9_loads_existing_rules_without_redefinition() -> None:
    integration, inventory, deduplication, corpus_validation = _load_inputs()

    rule_set = load_integrated_existing_rule_set(
        PRODUCTION,
        integration,
        inventory,
        deduplication,
        corpus_validation,
    )

    assert len(rule_set.rules) == 14
    assert [
        (rule.rule_id, rule.version, rule.normative_refs)
        for rule in rule_set.rules
    ] == [
        (item.rule_id, item.version, item.normative_refs)
        for item in inventory.rules
    ]


def test_b9_preserves_normative_evidence_gate() -> None:
    integration, inventory, deduplication, corpus_validation = _load_inputs()

    result = infer_integrated_existing_rule_facts(
        PRODUCTION,
        integration,
        inventory,
        deduplication,
        corpus_validation,
        {"taxpayer_type": "individual"},
        None,
    )

    assert result.matched_rules == []
    assert result.derivations == []
    assert any(
        trace.skipped_reason == "No se proporcionó evidencia de aplicabilidad normativa."
        for trace in result.traces
    )


def test_b9_executes_through_existing_rbr_reasoner() -> None:
    integration, inventory, deduplication, corpus_validation = _load_inputs()

    result = infer_integrated_existing_rule_facts(
        PRODUCTION,
        integration,
        inventory,
        deduplication,
        corpus_validation,
        {"taxpayer_type": "individual"},
        {"cff:articulo_1", "lfdc:articulo_2"},
    )

    matched = {item.rule_id for item in result.matched_rules}
    assert matched == {
        "PROFILE_INDIVIDUAL_001",
        "RIGHT_INFORMATION_ASSISTANCE_004",
        "RIGHT_TAX_DATA_CONFIDENTIALITY_005",
        "RIGHT_RESPECTFUL_TREATMENT_006",
    }
    assert result.requires_human_review is False


def test_b9_does_not_create_parallel_engine_or_temporal_shortcut() -> None:
    integration, _, _, corpus_validation = _load_inputs()

    assert integration.modifies_production_rules is False
    assert integration.creates_parallel_rule_engine is False
    assert integration.requires_applicable_normative_refs is True
    assert integration.temporal_policy_fail_closed is True
    assert all(
        item.inherits_temporal_fail_closed
        for item in integration.integrations
    )
    assert all(
        item.creates_duplicate_rule is False
        for item in integration.integrations
    )
    assert all(
        item.temporal_validity_confirmed is False
        and item.requires_case_date_validation is True
        for item in corpus_validation.existing_rule_validations
    )
