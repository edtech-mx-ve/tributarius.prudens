from __future__ import annotations

from pathlib import Path

from app.domain.primary_cbr_corpus_validation import PrimaryCBRCorpusValidationOutcome
from app.services.primary_cbr_corpus_validation import (
    load_primary_cbr_corpus_validation_report,
)
from app.services.primary_cbr_families import (
    load_primary_cbr_family_registry,
    validate_primary_cbr_family_registry,
)
from app.services.primary_cbr_inventory import load_current_cbr_inventory
from app.services.primary_cbr_problem_institution import (
    load_primary_cbr_problem_institution_classification,
)
from app.services.primary_legal_knowledge import (
    load_fiscal_problem_institution_taxonomy,
)

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "app" / "resources"


def _load_registry():
    return load_primary_cbr_family_registry(RESOURCES / "primary_cbr_families.json")


def test_c8_formalizes_exactly_12_existing_families_and_37_assignments() -> None:
    registry = _load_registry()
    inventory = load_current_cbr_inventory(RESOURCES / "current_cbr_inventory.json")

    assert registry.family_count == 12
    assert registry.assigned_situation_count == 37
    assert [item.family_id for item in registry.families] == (
        inventory.primary_knowledge_cbr_families
    )
    assert len(registry.assignments) == 37


def test_c8_primary_partitions_are_specific_and_reproducible() -> None:
    registry = _load_registry()

    assert registry.primary_family_coverage_count == 8
    assert registry.primary_family_counts == {
        "CBR-AUTORIDAD": 1,
        "CBR-CALCULO": 24,
        "CBR-DEFENSA": 2,
        "CBR-DERECHOS": 1,
        "CBR-DEUDA": 0,
        "CBR-INCUMPLIMIENTO": 1,
        "CBR-INTERPRETACION": 2,
        "CBR-OBLIGACION": 5,
        "CBR-PERFIL": 0,
        "CBR-SUJETO": 0,
        "CBR-TEMPORALIDAD": 0,
        "CBR-TRIBUTO": 1,
    }
    assert registry.secondary_only_family_ids == [
        "CBR-DEUDA",
        "CBR-PERFIL",
        "CBR-SUJETO",
        "CBR-TEMPORALIDAD",
    ]


def test_c8_uses_all_12_families_as_primary_or_related_facets() -> None:
    registry = _load_registry()
    known = {item.family_id for item in registry.families}

    assert set(registry.family_membership_counts) == known
    assert all(count > 0 for count in registry.family_membership_counts.values())
    assert all(item.primary_family_id == item.family_ids[0] for item in registry.assignments)
    assert all(set(item.family_ids) <= known for item in registry.assignments)


def test_c8_preserves_temporal_family_for_historical_rif_cases() -> None:
    registry = _load_registry()
    historical = {
        item.situation_id: item
        for item in registry.assignments
        if item.historical_regime_context
    }

    assert set(historical) == {
        "P-CBR-SIT-023",
        "P-CBR-SIT-024",
        "U-CBR-SIT-008",
    }
    assert all("CBR-TEMPORALIDAD" in item.family_ids for item in historical.values())
    assert historical["P-CBR-SIT-023"].corpus_validation_outcome == (
        PrimaryCBRCorpusValidationOutcome.BLOCKED_DEROGATED
    )
    assert historical["U-CBR-SIT-008"].corpus_validation_outcome == (
        PrimaryCBRCorpusValidationOutcome.BLOCKED_DEROGATED
    )


def test_c8_preserves_c7_validation_outcomes_without_promoting_cases() -> None:
    registry = _load_registry()
    outcomes = [item.corpus_validation_outcome for item in registry.assignments]

    assert outcomes.count(PrimaryCBRCorpusValidationOutcome.CONSISTENT) == 20
    assert outcomes.count(PrimaryCBRCorpusValidationOutcome.BLOCKED_DEROGATED) == 3
    assert outcomes.count(PrimaryCBRCorpusValidationOutcome.BLOCKED_CONTENT_MISMATCH) == 2
    assert outcomes.count(PrimaryCBRCorpusValidationOutcome.NO_EXPLICIT_CITATION) == 12
    assert not any(item.legal_similarity_enabled for item in registry.assignments)
    assert not any(item.operational_case_created for item in registry.assignments)


def test_c8_validates_against_c1_a6_c5_and_c7() -> None:
    registry = _load_registry()
    inventory = load_current_cbr_inventory(RESOURCES / "current_cbr_inventory.json")
    taxonomy = load_fiscal_problem_institution_taxonomy(
        RESOURCES / "fiscal_problem_institution_taxonomy.json"
    )
    classification = load_primary_cbr_problem_institution_classification(
        RESOURCES / "primary_cbr_problem_institution.json"
    )
    corpus_validation = load_primary_cbr_corpus_validation_report(
        RESOURCES / "primary_cbr_corpus_validation.json"
    )

    validate_primary_cbr_family_registry(
        registry,
        inventory,
        taxonomy,
        classification,
        corpus_validation,
    )

    assert registry.preserves_c7_validation_state
    assert registry.uses_only_c1_a6_family_ids
    assert not registry.enables_legal_similarity
    assert not registry.creates_operational_cases
    assert not registry.modifies_existing_cbr_engine
    assert not registry.can_control_legal_decision
