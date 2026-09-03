from pathlib import Path

from app.services.primary_cbr_fact_normalization import (
    load_primary_cbr_fact_normalization,
    validate_primary_cbr_fact_normalization,
)
from app.services.primary_cbr_inventory import load_current_cbr_inventory
from app.services.primary_cbr_source_situations import load_primary_cbr_situation_extraction

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "app" / "resources"


def _load_inputs():
    normalization = load_primary_cbr_fact_normalization(
        RESOURCES / "primary_cbr_normalized_facts.json"
    )
    prodecon = load_primary_cbr_situation_extraction(
        RESOURCES / "prodecon_cbr_situations.json"
    )
    unam = load_primary_cbr_situation_extraction(
        RESOURCES / "unam_cbr_practical_cases.json"
    )
    inventory = load_current_cbr_inventory(RESOURCES / "current_cbr_inventory.json")
    return normalization, prodecon, unam, inventory


def test_c4_normalizes_all_37_source_situations() -> None:
    normalization, prodecon, unam, inventory = _load_inputs()

    validate_primary_cbr_fact_normalization(
        normalization,
        prodecon,
        unam,
        inventory,
    )

    assert normalization.prodecon_situation_count == 24
    assert normalization.unam_situation_count == 13
    assert normalization.source_situation_count == 37
    assert normalization.normalized_situation_count == 37
    assert normalization.source_raw_fact_statement_count == 74
    assert normalization.normalized_fact_count > 100


def test_c4_every_source_statement_has_traceable_normalized_facts() -> None:
    normalization, prodecon, unam, _ = _load_inputs()
    source = {
        item.situation_id: item
        for item in [*prodecon.situations, *unam.situations]
    }

    for item in normalization.situations:
        original = source[item.situation_id]
        assert item.raw_fact_count == len(original.raw_fact_statements)
        assert {fact.raw_fact_index for fact in item.facts} == set(
            range(1, item.raw_fact_count + 1)
        )
        assert all(
            fact.source_text == original.raw_fact_statements[fact.raw_fact_index - 1]
            for fact in item.facts
        )
        assert item.raw_facts_fully_covered is True
        assert item.facts_normalized is True
        assert all(fact.source_asserted is True for fact in item.facts)
        assert all(fact.legal_inference_added is False for fact in item.facts)


def test_c4_prepares_only_existing_similarity_fields_and_defers_problem_type() -> None:
    normalization, _, _, inventory = _load_inputs()

    assert normalization.similarity_fields_from_c1 == inventory.similarity_fields
    assert normalization.required_case_fields == [
        "taxpayer_type",
        "activity",
        "tax",
        "problem_type",
        "fiscal_year",
    ]
    assert normalization.problem_type_deferred_to_c5 is True
    assert all(item.similarity_seed.problem_type is None for item in normalization.situations)
    assert all(
        "problem_type" in item.unresolved_required_case_fields
        for item in normalization.situations
    )


def test_c4_preserves_exact_isr_iva_and_taxpayer_seeds_when_source_is_specific() -> None:
    normalization, _, _, _ = _load_inputs()
    items = {item.situation_id: item for item in normalization.situations}

    assert items["P-CBR-SIT-021"].similarity_seed.taxpayer_type == "individual"
    assert items["P-CBR-SIT-021"].similarity_seed.tax == "ISR"
    assert (
        items["P-CBR-SIT-021"].similarity_seed.activity
        == "servicios profesionales independientes"
    )

    assert items["U-CBR-SIT-001"].similarity_seed.taxpayer_type == "legal_entity"
    assert items["U-CBR-SIT-001"].similarity_seed.tax == "ISR"
    assert items["U-CBR-SIT-001"].similarity_seed.fiscal_year == 2017

    assert items["U-CBR-SIT-013"].similarity_seed.taxpayer_type == "individual"
    assert items["U-CBR-SIT-013"].similarity_seed.tax == "IVA"
    assert items["U-CBR-SIT-013"].similarity_seed.activity == "servicios profesionales de auditoria"


def test_c4_preserves_historical_rif_without_claiming_current_validity() -> None:
    normalization, _, _, _ = _load_inputs()
    historical = [
        item for item in normalization.situations if item.historical_regime_context
    ]

    assert {item.situation_id for item in historical} == {
        "P-CBR-SIT-023",
        "P-CBR-SIT-024",
        "U-CBR-SIT-008",
    }
    for item in historical:
        assert any(
            fact.key == "regime_status" and fact.value == "historical"
            for fact in item.facts
        )
        assert item.corpus_validated is False
        assert item.operational_case_created is False


def test_c4_does_not_advance_c5_to_c10_or_modify_existing_cbr() -> None:
    normalization, _, _, inventory = _load_inputs()

    assert normalization.creates_operational_cases is False
    assert normalization.modifies_existing_cbr_engine is False
    assert normalization.source_is_normative_authority is False
    assert normalization.can_control_legal_decision is False
    assert inventory.source_tree_operational_case_count == 0
    assert all(item.problem_institution_classified is False for item in normalization.situations)
    assert all(item.normative_articles_linked is False for item in normalization.situations)
    assert all(item.corpus_validated is False for item in normalization.situations)
    assert all(item.cbr_family_assigned is False for item in normalization.situations)
    assert all(item.operational_case_created is False for item in normalization.situations)
