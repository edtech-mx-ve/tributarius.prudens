from pathlib import Path

from app.services.primary_legal_knowledge import load_primary_knowledge_map
from app.services.primary_rbs_families import (
    load_primary_rbs_family_registry,
    validate_primary_rbs_family_links,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "app" / "resources" / "primary_rbs_family_registry.json"
KNOWLEDGE_MAP_PATH = ROOT / "app" / "resources" / "primary_legal_knowledge_map.json"


def test_b2_registers_seventeen_general_families() -> None:
    registry = load_primary_rbs_family_registry(REGISTRY_PATH)

    assert registry.total_families == 17
    assert {family.family_id for family in registry.families} == {
        "R-PER",
        "R-SUJ",
        "R-TRI",
        "R-OBL",
        "R-DER",
        "R-REQ",
        "R-LIM",
        "R-EXC",
        "R-CAL",
        "R-DEU",
        "R-AUT",
        "R-COM",
        "R-INC",
        "R-SAN",
        "R-DEF",
        "R-INT",
        "R-TEM",
    }


def test_b2_covers_all_rbs_families_from_block_a() -> None:
    registry = load_primary_rbs_family_registry(REGISTRY_PATH)
    knowledge_map = load_primary_knowledge_map(KNOWLEDGE_MAP_PATH)

    validate_primary_rbs_family_links(registry, knowledge_map)


def test_b2_keeps_design_separate_from_rule_creation() -> None:
    registry = load_primary_rbs_family_registry(REGISTRY_PATH)

    assert registry.modifies_current_rules is False
    assert all(family.creates_rules is False for family in registry.families)


def test_b2_rule_prefixes_are_stable_and_unique() -> None:
    registry = load_primary_rbs_family_registry(REGISTRY_PATH)
    prefixes = [family.rule_prefix for family in registry.families]

    assert len(prefixes) == len(set(prefixes))
    assert all(
        family.rule_prefix == f"{family.family_id}-"
        for family in registry.families
    )


def test_b2_includes_future_generalization_families() -> None:
    registry = load_primary_rbs_family_registry(REGISTRY_PATH)
    family_ids = {family.family_id for family in registry.families}

    assert {"R-REQ", "R-LIM", "R-EXC", "R-COM"} <= family_ids
