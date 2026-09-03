from pathlib import Path

import pytest

from app.services.primary_cbr_inventory import (
    CurrentCBRInventoryError,
    load_current_cbr_inventory,
    validate_current_cbr_inventory,
)

ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "app" / "resources" / "current_cbr_inventory.json"


def test_c1_inventory_is_exact_for_block_b_baseline() -> None:
    inventory = load_current_cbr_inventory(INVENTORY_PATH)

    assert inventory.baseline_commit == "b65dc014e57042ef4826354fa5ccb9b0610c0c4f"
    assert len(inventory.components) == 18
    assert inventory.fixture_case_count == 3
    assert inventory.source_tree_operational_case_count == 0
    assert inventory.runtime_database_case_count_known is False
    assert inventory.can_modify_existing_cbr is False


def test_c1_inventory_matches_real_cbr_contracts() -> None:
    inventory = load_current_cbr_inventory(INVENTORY_PATH)

    validate_current_cbr_inventory(inventory, ROOT)


def test_c1_records_current_similarity_and_reuse_thresholds() -> None:
    inventory = load_current_cbr_inventory(INVENTORY_PATH)

    assert inventory.minimum_retrieval_similarity == 0.60
    assert inventory.minimum_reuse_similarity == 0.75
    assert inventory.critical_fields == [
        "taxpayer_type",
        "tax",
        "problem_type",
    ]
    assert inventory.field_weights == {
        "taxpayer_type": 0.18,
        "activity": 0.16,
        "tax": 0.18,
        "problem_type": 0.18,
        "authority_act": 0.10,
        "procedural_stage": 0.10,
        "fiscal_year": 0.10,
    }


def test_c1_records_current_safety_and_authority_boundary() -> None:
    inventory = load_current_cbr_inventory(INVENTORY_PATH)

    assert inventory.retrievable_statuses == ["active", "historical"]
    assert inventory.non_retrievable_statuses == ["superseded", "invalidated"]
    assert inventory.requires_anonymized_cases is True
    assert inventory.requires_validated_cases is True
    assert inventory.retention_candidate_status == "pending_review"
    assert inventory.retention_proposed_case_status == "historical"
    assert inventory.cbr_is_normative_authority is False


def test_c1_records_primary_family_references_without_inventing_cases() -> None:
    inventory = load_current_cbr_inventory(INVENTORY_PATH)

    assert inventory.primary_knowledge_cbr_family_count == 12
    assert inventory.primary_family_registry_present_at_baseline is False
    assert set(inventory.primary_knowledge_cbr_families) == {
        "CBR-AUTORIDAD",
        "CBR-CALCULO",
        "CBR-DEFENSA",
        "CBR-DERECHOS",
        "CBR-DEUDA",
        "CBR-INCUMPLIMIENTO",
        "CBR-INTERPRETACION",
        "CBR-OBLIGACION",
        "CBR-PERFIL",
        "CBR-SUJETO",
        "CBR-TEMPORALIDAD",
        "CBR-TRIBUTO",
    }


def test_c1_detects_missing_component(tmp_path: Path) -> None:
    inventory = load_current_cbr_inventory(INVENTORY_PATH)
    missing_root = tmp_path / "repo"
    missing_root.mkdir()

    with pytest.raises(CurrentCBRInventoryError, match="Faltan componentes"):
        validate_current_cbr_inventory(inventory, missing_root)
