from pathlib import Path

from app.domain.primary_legal_knowledge import FiscalProblemInstitutionKind
from app.services.primary_cbr_fact_normalization import load_primary_cbr_fact_normalization
from app.services.primary_cbr_inventory import load_current_cbr_inventory
from app.services.primary_cbr_problem_institution import (
    load_primary_cbr_problem_institution_classification,
    validate_primary_cbr_problem_institution_classification,
)
from app.services.primary_legal_knowledge import load_fiscal_problem_institution_taxonomy

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "app" / "resources"


def _load_inputs():
    classification = load_primary_cbr_problem_institution_classification(
        RESOURCES / "primary_cbr_problem_institution.json"
    )
    normalization = load_primary_cbr_fact_normalization(
        RESOURCES / "primary_cbr_normalized_facts.json"
    )
    taxonomy = load_fiscal_problem_institution_taxonomy(
        RESOURCES / "fiscal_problem_institution_taxonomy.json"
    )
    inventory = load_current_cbr_inventory(RESOURCES / "current_cbr_inventory.json")
    return classification, normalization, taxonomy, inventory


def test_c5_classifies_all_37_situations_against_existing_a6_taxonomy() -> None:
    classification, normalization, taxonomy, inventory = _load_inputs()

    validate_primary_cbr_problem_institution_classification(
        classification,
        normalization,
        taxonomy,
        inventory,
    )

    assert classification.taxonomy_concept_count == 12
    assert classification.taxonomy_problem_count == 6
    assert classification.taxonomy_institution_count == 6
    assert classification.source_situation_count == 37
    assert classification.classified_situation_count == 37


def test_c5_uses_only_a6_concepts_eligible_for_each_source_entry() -> None:
    classification, _, taxonomy, _ = _load_inputs()
    concepts = {concept.concept_id: concept for concept in taxonomy.concepts}

    for item in classification.classifications:
        for match in [*item.problem_matches, *item.institution_matches]:
            concept = concepts[match.concept_id]
            assert match.label == concept.label
            assert match.kind is concept.kind
            assert item.source_entry_id in concept.primary_entries
            assert match.taxonomic_only is True
            assert match.requires_normative_validation is True
            assert match.can_control_legal_decision is False


def test_c5_fills_problem_type_only_from_primary_problem_and_preserves_c4_evidence() -> None:
    classification, normalization, _, _ = _load_inputs()
    normalized = {item.situation_id: item for item in normalization.situations}

    for item in classification.classifications:
        previous = normalized[item.situation_id]
        if item.primary_problem_id is None:
            assert item.similarity_seed.problem_type is None
            assert "problem_type" in item.unresolved_required_case_fields
        else:
            assert item.similarity_seed.problem_type == item.primary_problem_id
            assert "problem_type" not in item.unresolved_required_case_fields
            primary = next(match for match in item.problem_matches if match.primary)
            assert item.similarity_seed.evidence_fact_ids["problem_type"] == (
                primary.evidence_fact_ids
            )

        for field_name in (
            "taxpayer_type",
            "activity",
            "tax",
            "authority_act",
            "procedural_stage",
            "fiscal_year",
        ):
            assert getattr(item.similarity_seed, field_name) == getattr(
                previous.similarity_seed, field_name
            )


def test_c5_preserves_explicit_no_match_instead_of_inventing_taxonomy() -> None:
    classification, _, _, _ = _load_inputs()
    items = {item.situation_id: item for item in classification.classifications}

    no_problem_ids = {
        item.situation_id
        for item in classification.classifications
        if item.primary_problem_id is None
    }
    assert no_problem_ids == {
        "P-CBR-SIT-003",
        "P-CBR-SIT-004",
    }
    assert {
        item.situation_id
        for item in classification.classifications
        if item.primary_institution_id is None
    } == {
        "P-CBR-SIT-001",
        "P-CBR-SIT-002",
        "P-CBR-SIT-015",
        "P-CBR-SIT-016",
        "P-CBR-SIT-017",
        "P-CBR-SIT-018",
    }
    assert items["P-CBR-SIT-003"].problem_no_exact_match_reason
    assert items["P-CBR-SIT-015"].institution_no_exact_match_reason
    assert classification.creates_new_taxonomy_concepts is False


def test_c5_assigns_expected_taxonomic_problem_and_institution_for_key_cases() -> None:
    classification, _, _, _ = _load_inputs()
    items = {item.situation_id: item for item in classification.classifications}

    assert items["P-CBR-SIT-012"].primary_problem_id == "incumplimiento_fiscal"
    assert items["P-CBR-SIT-012"].primary_institution_id == "deuda_tributaria"
    assert items["P-CBR-SIT-015"].primary_problem_id == "defensa_contribuyente"
    assert items["P-CBR-SIT-017"].primary_problem_id == "interpretacion_fiscal"
    assert items["P-CBR-SIT-021"].primary_problem_id == "determinacion_contribucion"
    assert items["P-CBR-SIT-021"].primary_institution_id == "regimen_isr"
    assert items["U-CBR-SIT-001"].primary_problem_id == "determinacion_contribucion"
    assert items["U-CBR-SIT-001"].primary_institution_id == "regimen_isr"
    assert items["U-CBR-SIT-013"].primary_institution_id == "tributo"
    assert all(
        match.kind is FiscalProblemInstitutionKind.PROBLEM
        for match in items["P-CBR-SIT-012"].problem_matches
    )


def test_c5_preserves_historical_rif_and_defers_c6_to_c10() -> None:
    classification, _, _, _ = _load_inputs()
    historical = [
        item for item in classification.classifications if item.historical_regime_context
    ]

    assert {item.situation_id for item in historical} == {
        "P-CBR-SIT-023",
        "P-CBR-SIT-024",
        "U-CBR-SIT-008",
    }
    assert all(item.primary_problem_id == "determinacion_contribucion" for item in historical)
    assert all(item.primary_institution_id == "regimen_isr" for item in historical)
    assert all(item.corpus_validated is False for item in historical)

    assert classification.links_normative_articles is False
    assert classification.validates_current_law is False
    assert classification.assigns_cbr_families is False
    assert classification.creates_operational_cases is False
    assert classification.modifies_existing_cbr_engine is False
    assert classification.source_is_normative_authority is False
    assert classification.can_control_legal_decision is False
    assert all(item.normative_articles_linked is False for item in classification.classifications)
    assert all(item.corpus_validated is False for item in classification.classifications)
    assert all(item.cbr_family_assigned is False for item in classification.classifications)
    assert all(item.operational_case_created is False for item in classification.classifications)
