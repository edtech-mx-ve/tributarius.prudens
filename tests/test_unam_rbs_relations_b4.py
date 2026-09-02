from pathlib import Path

from app.services.primary_legal_knowledge import load_primary_knowledge_map
from app.services.primary_rbs_families import load_primary_rbs_family_registry
from app.services.primary_rbs_source_relations import (
    load_primary_rbs_relation_extraction,
    validate_primary_rbs_relation_extraction,
)

ROOT = Path(__file__).resolve().parents[1]
RELATIONS_PATH = ROOT / "app" / "resources" / "unam_rbs_relations.json"
KNOWLEDGE_PATH = ROOT / "app" / "resources" / "primary_legal_knowledge_map.json"
FAMILIES_PATH = ROOT / "app" / "resources" / "primary_rbs_family_registry.json"


def test_b4_extracts_relations_from_all_seven_unam_chapters() -> None:
    extraction = load_primary_rbs_relation_extraction(RELATIONS_PATH)

    assert extraction.source.value == "unam"
    assert extraction.source_entry_count == 7
    assert {relation.source_entry_id for relation in extraction.relations} == {
        "UNAM-I",
        "UNAM-II",
        "UNAM-III",
        "UNAM-IV",
        "UNAM-V",
        "UNAM-VI",
        "UNAM-VII",
    }


def test_b4_relations_are_source_grounded_against_block_a_and_b2() -> None:
    extraction = load_primary_rbs_relation_extraction(RELATIONS_PATH)
    knowledge_map = load_primary_knowledge_map(KNOWLEDGE_PATH)
    family_registry = load_primary_rbs_family_registry(FAMILIES_PATH)

    validate_primary_rbs_relation_extraction(
        extraction,
        knowledge_map,
        family_registry,
    )


def test_b4_is_pre_deduplication_and_non_determinative() -> None:
    extraction = load_primary_rbs_relation_extraction(RELATIONS_PATH)

    assert extraction.deduplicated is False
    assert all(relation.requires_normative_validation for relation in extraction.relations)
    assert all(not relation.can_control_legal_decision for relation in extraction.relations)


def test_b4_preserves_interpretation_and_temporal_links() -> None:
    extraction = load_primary_rbs_relation_extraction(RELATIONS_PATH)

    interpretation = [
        relation
        for relation in extraction.relations
        if relation.source_entry_id == "UNAM-II"
    ]
    calculation = [
        relation
        for relation in extraction.relations
        if relation.source_entry_id == "UNAM-V"
    ]

    assert interpretation
    assert all("R-INT" in relation.rbs_families for relation in interpretation)
    assert all(
        "REL-NOR-INT" in relation.canonical_relation_ids
        for relation in interpretation
    )
    assert calculation
    assert any(
        "REL-REG-REQ" in relation.canonical_relation_ids
        for relation in calculation
    )


def test_b4_supports_multiple_relations_per_chapter() -> None:
    extraction = load_primary_rbs_relation_extraction(RELATIONS_PATH)
    counts = {
        entry_id: sum(
            relation.source_entry_id == entry_id
            for relation in extraction.relations
        )
        for entry_id in {relation.source_entry_id for relation in extraction.relations}
    }

    assert len(extraction.relations) == 14
    assert all(count == 2 for count in counts.values())
