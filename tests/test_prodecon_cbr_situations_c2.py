from pathlib import Path

from app.domain.primary_cbr_source_situations import PrimaryCBRSituationKind
from app.services.primary_cbr_inventory import load_current_cbr_inventory
from app.services.primary_cbr_source_situations import (
    load_primary_cbr_situation_extraction,
    validate_prodecon_cbr_situation_extraction,
)
from app.services.primary_legal_knowledge import load_primary_knowledge_map

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "app" / "resources"


def _load_inputs():
    extraction = load_primary_cbr_situation_extraction(
        RESOURCES / "prodecon_cbr_situations.json"
    )
    knowledge_map = load_primary_knowledge_map(
        RESOURCES / "primary_legal_knowledge_map.json"
    )
    inventory = load_current_cbr_inventory(RESOURCES / "current_cbr_inventory.json")
    return extraction, knowledge_map, inventory


def test_c2_covers_all_12_prodecon_sections_with_24_situations() -> None:
    extraction, knowledge_map, inventory = _load_inputs()

    validate_prodecon_cbr_situation_extraction(extraction, knowledge_map, inventory)

    assert extraction.source_entry_count == 12
    assert extraction.expected_situations_per_entry == 2
    assert extraction.situation_count == 24
    assert [item.situation_id for item in extraction.situations] == [
        f"P-CBR-SIT-{index:03d}" for index in range(1, 25)
    ]


def test_c2_preserves_exact_primary_prodecon_entry_titles_and_order() -> None:
    extraction, knowledge_map, _ = _load_inputs()
    prodecon = {
        item.entry_id: (item.order, item.title)
        for item in knowledge_map.entries
        if item.manual.value == "prodecon"
    }

    assert set(prodecon) == {f"PRODECON-{index:02d}" for index in range(1, 13)}
    for situation in extraction.situations:
        assert (
            situation.source_section_order,
            situation.source_section_title,
        ) == prodecon[situation.source_entry_id]


def test_c2_is_source_extraction_and_does_not_create_operational_cases() -> None:
    extraction, _, inventory = _load_inputs()

    assert extraction.facts_normalized is False
    assert extraction.problems_institutions_classified is False
    assert extraction.normative_articles_linked is False
    assert extraction.corpus_validated is False
    assert extraction.cbr_families_assigned is False
    assert extraction.operational_cases_created is False
    assert inventory.source_tree_operational_case_count == 0
    assert all(item.eligible_for_operational_cbr is False for item in extraction.situations)


def test_c2_requires_all_downstream_legal_validation_gates() -> None:
    extraction, _, _ = _load_inputs()

    for situation in extraction.situations:
        assert situation.temporal_review_required is True
        assert situation.requires_fact_normalization is True
        assert situation.requires_problem_institution_classification is True
        assert situation.requires_normative_article_linkage is True
        assert situation.requires_corpus_validation is True
        assert situation.can_control_legal_decision is False
        assert situation.source_pages == sorted(set(situation.source_pages))
        assert situation.raw_fact_statements


def test_c2_preserves_rif_as_historical_source_context() -> None:
    extraction, _, _ = _load_inputs()
    rif = [
        item for item in extraction.situations if item.source_entry_id == "PRODECON-12"
    ]
    non_rif = [
        item for item in extraction.situations if item.source_entry_id != "PRODECON-12"
    ]

    assert len(rif) == 2
    assert all(item.kind is PrimaryCBRSituationKind.HISTORICAL_REGIME for item in rif)
    assert all(item.historical_regime_context is True for item in rif)
    assert all(item.historical_regime_context is False for item in non_rif)


def test_c2_keeps_prodecon_outside_normative_authority_boundary() -> None:
    extraction, _, inventory = _load_inputs()

    assert extraction.source_is_normative_authority is False
    assert extraction.source_can_control_legal_decision is False
    assert inventory.cbr_is_normative_authority is False
