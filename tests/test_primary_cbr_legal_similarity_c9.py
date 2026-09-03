from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.cbr import CaseField
from app.domain.primary_cbr_legal_similarity import PrimaryCBRLegalSimilarityDecision
from app.services.primary_cbr_corpus_validation import (
    load_primary_cbr_corpus_validation_report,
)
from app.services.primary_cbr_families import load_primary_cbr_family_registry
from app.services.primary_cbr_legal_similarity import (
    COMPONENT_WEIGHTS,
    load_primary_cbr_legal_similarity_index,
    score_primary_cbr_legal_similarity,
    validate_primary_cbr_legal_similarity_index,
)
from app.services.primary_cbr_problem_institution import (
    load_primary_cbr_problem_institution_classification,
)
from cbr.engine import MINIMUM_CBR_SIMILARITY
from cbr.similarity import FIELD_WEIGHTS, partial_case_similarity

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "app" / "resources"


def _load_index():
    return load_primary_cbr_legal_similarity_index(
        RESOURCES / "primary_cbr_legal_similarity.json"
    )


def _profile(index, situation_id: str):
    return next(item for item in index.profiles if item.situation_id == situation_id)


def test_c9_extends_existing_similarity_contract_without_replacing_it() -> None:
    index = _load_index()

    assert index.existing_similarity_module == "cbr.similarity"
    assert index.field_weight_source == "cbr.similarity.FIELD_WEIGHTS"
    assert index.minimum_similarity == MINIMUM_CBR_SIMILARITY == 0.60
    assert index.component_weights == COMPONENT_WEIGHTS
    assert sum(FIELD_WEIGHTS.values()) == pytest.approx(1.0)
    assert set(FIELD_WEIGHTS) == set(CaseField)
    assert index.extends_existing_cbr_similarity
    assert not index.replaces_existing_cbr_similarity
    assert not index.changes_existing_field_weights
    assert not index.changes_existing_retrieval_threshold


def test_c9_partial_similarity_reuses_existing_weights_and_ignores_unknown_fields() -> None:
    left = {
        CaseField.TAXPAYER_TYPE: "individual",
        CaseField.ACTIVITY: None,
        CaseField.TAX: "ISR",
        CaseField.PROBLEM_TYPE: "determinacion_contribucion",
        CaseField.AUTHORITY_ACT: None,
        CaseField.PROCEDURAL_STAGE: None,
        CaseField.FISCAL_YEAR: None,
    }
    right = dict(left)

    similarity, fields = partial_case_similarity(left, right)

    assert similarity == 1.0
    active = {item.field for item in fields if item.weight > 0}
    assert active == {
        CaseField.TAXPAYER_TYPE,
        CaseField.TAX,
        CaseField.PROBLEM_TYPE,
    }
    assert next(item for item in fields if item.field == CaseField.ACTIVITY).weight == 0.0


def test_c9_compares_all_37_profiles_and_partitions_pairs_fail_closed() -> None:
    index = _load_index()

    assert index.profile_count == 37
    assert index.total_pair_count == 666
    assert index.same_primary_family_pair_count == 288
    assert index.blocked_primary_family_pair_count == 378
    assert index.blocked_critical_conflict_pair_count == 88
    assert index.blocked_historical_context_pair_count == 63
    assert index.below_threshold_pair_count == 1
    assert index.eligible_pair_count == 136
    assert index.stored_neighbor_link_count == 133


def test_c9_rejects_observable_critical_conflicts_and_historical_mismatch() -> None:
    index = _load_index()

    legal_entity = _profile(index, "U-CBR-SIT-001")
    individual = _profile(index, "U-CBR-SIT-006")
    decision, _, _, _, _, _, conflicts = score_primary_cbr_legal_similarity(
        legal_entity,
        individual,
    )
    assert decision is PrimaryCBRLegalSimilarityDecision.BLOCKED_CRITICAL_CONFLICT
    assert CaseField.TAXPAYER_TYPE in conflicts

    historical_rif = _profile(index, "U-CBR-SIT-008")
    current_professional = _profile(index, "U-CBR-SIT-009")
    decision, *_ = score_primary_cbr_legal_similarity(historical_rif, current_professional)
    assert decision is PrimaryCBRLegalSimilarityDecision.BLOCKED_HISTORICAL_CONTEXT


def test_c9_ranks_legal_analogies_deterministically_with_family_and_taxonomy() -> None:
    index = _load_index()
    neighbors = next(item for item in index.neighbors if item.situation_id == "U-CBR-SIT-009")

    assert neighbors.returned_count == 5
    assert neighbors.matches[0].situation_id == "P-CBR-SIT-009"
    assert neighbors.matches[0].similarity == 1.0
    assert neighbors.matches[0].existing_cbr_field_similarity == 1.0
    assert neighbors.matches[0].family_overlap_similarity == 1.0
    assert neighbors.matches[0].taxonomy_overlap_similarity == 1.0


def test_c9_preserves_c7_blocks_and_never_promotes_operational_reuse() -> None:
    index = _load_index()
    historical = next(item for item in index.neighbors if item.situation_id == "U-CBR-SIT-008")

    assert [item.situation_id for item in historical.matches] == [
        "P-CBR-SIT-023",
        "P-CBR-SIT-024",
    ]
    assert all(item.requires_temporal_review for item in historical.matches)
    assert all(item.requires_normative_review for item in historical.matches)
    professional = next(
        item for item in index.neighbors if item.situation_id == "U-CBR-SIT-009"
    )
    assert any(not item.requires_normative_review for item in professional.matches)
    assert not any(
        item.operational_reuse_allowed
        for group in index.neighbors
        for item in group.matches
    )
    assert not index.creates_operational_cases
    assert not index.can_control_legal_decision


def test_c9_is_reproducible_from_c5_c7_and_c8() -> None:
    index = _load_index()
    c5 = load_primary_cbr_problem_institution_classification(
        RESOURCES / "primary_cbr_problem_institution.json"
    )
    c7 = load_primary_cbr_corpus_validation_report(
        RESOURCES / "primary_cbr_corpus_validation.json"
    )
    c8 = load_primary_cbr_family_registry(RESOURCES / "primary_cbr_families.json")

    validate_primary_cbr_legal_similarity_index(index, c5, c7, c8)
