from pathlib import Path

import pytest

from app.core.config import Settings
from app.services.primary_rbs_inventory import load_current_production_rule_set
from app.services.rule_engine import evaluate_rules

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "app" / "resources" / "current_rbs_inventory.json"
PRODUCTION_DIR = ROOT / "rules" / "production"


def test_production_rbs_bundle_contains_exact_b1_rules() -> None:
    rule_set = load_current_production_rule_set(
        INVENTORY,
        PRODUCTION_DIR,
    )

    assert rule_set.schema_version == "1.0"
    assert len(rule_set.rules) == 14


def test_development_default_preserves_single_example_rule_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RUNTIME_RULE_SET_PATH", raising=False)

    settings = Settings(_env_file=None)

    assert settings.runtime_rule_set_path == "rules/examples/basic_obligations.json"


def test_production_settings_point_to_b1_inventory() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
    )

    assert (
        settings.runtime_rbs_inventory_path
        == "app/resources/current_rbs_inventory.json"
    )
    assert settings.runtime_rule_set_dir == "rules/production"


def test_production_rbs_executes_chained_professional_reasoning() -> None:
    rule_set = load_current_production_rule_set(
        INVENTORY,
        PRODUCTION_DIR,
    )

    result = evaluate_rules(
        rule_set,
        facts={
            "taxpayer_type": "individual",
            "income_type": "independent_professional_service",
        },
        applicable_normative_refs={
            "cff:articulo_1",
            "lisr:articulo_100",
            "lisr:articulo_110",
            "lfdc:articulo_2",
        },
    )

    conclusions = {
        item.conclusion_code
        for item in result.matched_rules
    }

    expected = {
        "individual_taxpayer_profile",
        "professional_service_income",
        "isr_professional_payment_obligation",
        "rfc_registration_obligation",
        "accounting_obligation",
        "income_cfdi_obligation",
        "right_information_and_assistance",
        "right_tax_data_confidentiality",
        "right_respectful_treatment",
    }

    assert expected.issubset(conclusions)
    assert len(result.derivations) >= len(expected)
    assert result.requires_human_review is False
