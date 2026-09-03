from pathlib import Path

from app.domain.primary_cbr_source_situations import PrimaryCBRSituationKind
from app.services.primary_cbr_inventory import load_current_cbr_inventory
from app.services.primary_cbr_source_situations import load_primary_cbr_situation_extraction
from app.services.primary_cbr_unam_cases import validate_unam_practical_case_extraction
from app.services.primary_legal_knowledge import load_primary_knowledge_map

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "app" / "resources"


def _load_inputs():
    extraction = load_primary_cbr_situation_extraction(
        RESOURCES / "unam_cbr_practical_cases.json"
    )
    knowledge_map = load_primary_knowledge_map(
        RESOURCES / "primary_legal_knowledge_map.json"
    )
    inventory = load_current_cbr_inventory(RESOURCES / "current_cbr_inventory.json")
    return extraction, knowledge_map, inventory


def test_c3_extracts_exact_13_explicit_unam_chapter_v_cases() -> None:
    extraction, knowledge_map, inventory = _load_inputs()

    validate_unam_practical_case_extraction(extraction, knowledge_map, inventory)

    assert extraction.source_entry_count == 1
    assert extraction.expected_situations_per_entry == 13
    assert extraction.situation_count == 13
    assert [item.situation_id for item in extraction.situations] == [
        f"U-CBR-SIT-{index:03d}" for index in range(1, 14)
    ]
    assert {item.source_entry_id for item in extraction.situations} == {"UNAM-V"}


def test_c3_preserves_unam_chapter_v_primary_metadata() -> None:
    extraction, knowledge_map, _ = _load_inputs()
    chapter_v = next(item for item in knowledge_map.entries if item.entry_id == "UNAM-V")

    assert chapter_v.order == 5
    assert chapter_v.title == "Cálculo de contribuciones"
    assert all(item.source_section_order == chapter_v.order for item in extraction.situations)
    assert all(item.source_section_title == chapter_v.title for item in extraction.situations)


def test_c3_preserves_case_distribution_from_unam_manual() -> None:
    extraction, _, _ = _load_inputs()

    moral_isr = extraction.situations[:5]
    physical_isr = extraction.situations[5:11]
    iva = extraction.situations[11:]

    assert len(moral_isr) == 5
    assert len(physical_isr) == 6
    assert len(iva) == 2
    assert all("ISR personas morales" in item.source_locator for item in moral_isr)
    assert all("ISR personas físicas" in item.source_locator for item in physical_isr)
    assert all("IVA" in item.source_locator for item in iva)


def test_c3_preserves_rif_case_as_historical_regime_context() -> None:
    extraction, _, _ = _load_inputs()
    rif = next(item for item in extraction.situations if item.situation_id == "U-CBR-SIT-008")

    assert rif.kind is PrimaryCBRSituationKind.HISTORICAL_REGIME
    assert rif.historical_regime_context is True
    assert all(
        item.historical_regime_context is False
        for item in extraction.situations
        if item.situation_id != rif.situation_id
    )


def test_c3_is_source_extraction_and_does_not_create_operational_cases() -> None:
    extraction, _, inventory = _load_inputs()

    assert extraction.facts_normalized is False
    assert extraction.problems_institutions_classified is False
    assert extraction.normative_articles_linked is False
    assert extraction.corpus_validated is False
    assert extraction.cbr_families_assigned is False
    assert extraction.operational_cases_created is False
    assert inventory.source_tree_operational_case_count == 0
    assert all(item.eligible_for_operational_cbr is False for item in extraction.situations)


def test_c3_requires_downstream_gates_and_keeps_unam_non_normative() -> None:
    extraction, _, inventory = _load_inputs()

    for item in extraction.situations:
        assert item.temporal_review_required is True
        assert item.requires_fact_normalization is True
        assert item.requires_problem_institution_classification is True
        assert item.requires_normative_article_linkage is True
        assert item.requires_corpus_validation is True
        assert item.can_control_legal_decision is False
        assert item.source_pages == sorted(set(item.source_pages))
        assert item.raw_fact_statements

    assert extraction.source_is_normative_authority is False
    assert extraction.source_can_control_legal_decision is False
    assert inventory.cbr_is_normative_authority is False
