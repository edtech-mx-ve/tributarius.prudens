from pathlib import Path

import pytest

from app.services.primary_rbs_inventory import (
    CurrentRBSInventoryError,
    load_current_rbs_inventory,
    validate_current_rbs_inventory,
)

ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "app" / "resources" / "current_rbs_inventory.json"
PRODUCTION_DIR = ROOT / "rules" / "production"


def test_b1_inventory_is_exact_for_baseline() -> None:
    inventory = load_current_rbs_inventory(INVENTORY_PATH)

    assert inventory.baseline_commit == "23eec1bbc48c95bb0dde383530e06884348e6905"
    assert inventory.total_rules == 14
    assert len(inventory.production_rule_files) == 4
    assert inventory.can_modify_production_rules is False


def test_b1_inventory_matches_real_production_rules() -> None:
    inventory = load_current_rbs_inventory(INVENTORY_PATH)

    validate_current_rbs_inventory(inventory, PRODUCTION_DIR)


def test_b1_inventory_preserves_current_distribution() -> None:
    inventory = load_current_rbs_inventory(INVENTORY_PATH)
    counts: dict[str, int] = {}
    for rule in inventory.rules:
        counts[rule.source_file] = counts.get(rule.source_file, 0) + 1

    assert counts == {
        "mvp_income_classification.json": 3,
        "mvp_isr_professional.json": 2,
        "mvp_obligations_rights.json": 6,
        "mvp_taxpayer_profile.json": 3,
    }


def test_b1_inventory_records_current_normative_coverage() -> None:
    inventory = load_current_rbs_inventory(INVENTORY_PATH)
    refs = {ref for rule in inventory.rules for ref in rule.normative_refs}

    assert refs == {
        "cff:articulo_1",
        "cff:articulo_2",
        "lfdc:articulo_2",
        "lisr:articulo_94",
        "lisr:articulo_100",
        "lisr:articulo_110",
        "lisr:articulo_114",
    }


def test_b1_detects_inventory_drift(tmp_path: Path) -> None:
    inventory = load_current_rbs_inventory(INVENTORY_PATH)
    production = tmp_path / "production"
    production.mkdir()
    for source in PRODUCTION_DIR.glob("*.json"):
        (production / source.name).write_bytes(source.read_bytes())

    (production / "unexpected.json").write_text(
        '{"schema_version":"1.0","rules":[]}',
        encoding="utf-8",
    )

    with pytest.raises(CurrentRBSInventoryError):
        validate_current_rbs_inventory(inventory, production)
