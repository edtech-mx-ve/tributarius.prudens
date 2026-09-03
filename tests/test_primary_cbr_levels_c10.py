from __future__ import annotations

from pathlib import Path

from app.domain.cbr import CBRCase
from app.domain.primary_cbr_corpus_validation import PrimaryCBRCorpusValidationOutcome
from app.domain.primary_cbr_levels import (
    PrimaryCBRKnowledgeLevel,
    PrimaryCBROperationalBlocker,
)
from app.services.primary_cbr_corpus_validation import (
    load_primary_cbr_corpus_validation_report,
)
from app.services.primary_cbr_legal_similarity import (
    load_primary_cbr_legal_similarity_index,
)
from app.services.primary_cbr_levels import (
    REQUIRED_OPERATIONAL_CASE_FIELDS,
    load_primary_cbr_level_registry,
    validate_primary_cbr_level_registry,
)
from app.services.primary_cbr_normative_citations import (
    load_primary_cbr_normative_citation_linkage,
)

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "app" / "resources"


def _load_registry():
    return load_primary_cbr_level_registry(RESOURCES / "primary_cbr_levels.json")


def _assessment(registry, situation_id: str):
    return next(item for item in registry.assessments if item.situation_id == situation_id)


def test_c10_creates_three_levels_with_fail_closed_counts() -> None:
    registry = _load_registry()

    assert registry.source_situation_count == 37
    assert registry.primary_membership_count == 37
    assert registry.validated_membership_count == 20
    assert registry.operational_membership_count == 0
    assert registry.highest_level_counts == {
        "primary": 17,
        "validated": 20,
        "operational": 0,
    }
    assert registry.operational_shape_complete_count == 7
    assert registry.validated_shape_complete_count == 6


def test_c10_validated_level_is_exactly_c7_consistent_corpus_validation() -> None:
    registry = _load_registry()
    c7 = load_primary_cbr_corpus_validation_report(
        RESOURCES / "primary_cbr_corpus_validation.json"
    )
    expected = {
        item.situation_id
        for item in c7.situations
        if item.corpus_validated
        and item.validation_outcome is PrimaryCBRCorpusValidationOutcome.CONSISTENT
    }
    actual = {
        item.situation_id
        for item in registry.assessments
        if item.validated_level_eligible
    }

    assert actual == expected
    assert len(actual) == 20
    assert all(
        item.highest_level is PrimaryCBRKnowledgeLevel.VALIDATED
        for item in registry.assessments
        if item.situation_id in actual
    )


def test_c10_identifies_six_validated_cases_with_complete_cbr_shape_but_does_not_promote() -> None:
    registry = _load_registry()
    complete = {
        item.situation_id
        for item in registry.assessments
        if item.validated_level_eligible and not item.unresolved_required_case_fields
    }

    assert complete == {
        "U-CBR-SIT-001",
        "U-CBR-SIT-002",
        "U-CBR-SIT-003",
        "U-CBR-SIT-005",
        "U-CBR-SIT-007",
        "U-CBR-SIT-011",
    }
    for situation_id in complete:
        item = _assessment(registry, situation_id)
        assert PrimaryCBROperationalBlocker.TEMPORAL_VALIDATION_PENDING in (
            item.operational_blockers
        )
        assert PrimaryCBROperationalBlocker.RESOLUTION_OUTCOME_NOT_VERIFIED in (
            item.operational_blockers
        )
        assert PrimaryCBROperationalBlocker.ANONYMIZATION_REVIEW_PENDING in (
            item.operational_blockers
        )
        assert not item.operational_level_eligible


def test_c10_preserves_c7_blocks_and_rif_never_becomes_operational() -> None:
    registry = _load_registry()

    no_citation = _assessment(registry, "P-CBR-SIT-002")
    assert no_citation.highest_level is PrimaryCBRKnowledgeLevel.PRIMARY
    assert PrimaryCBROperationalBlocker.CORPUS_NOT_VALIDATED in (
        no_citation.operational_blockers
    )

    for situation_id in {"P-CBR-SIT-023", "U-CBR-SIT-008"}:
        rif = _assessment(registry, situation_id)
        assert rif.historical_regime_context
        assert rif.highest_level is PrimaryCBRKnowledgeLevel.PRIMARY
        assert not rif.validated_level_eligible
        assert not rif.operational_level_eligible
        assert PrimaryCBROperationalBlocker.CORPUS_NOT_VALIDATED in (
            rif.operational_blockers
        )


def test_c10_reuses_existing_cbrcase_contract_without_persisting_cases() -> None:
    registry = _load_registry()

    assert set(REQUIRED_OPERATIONAL_CASE_FIELDS) <= set(CBRCase.model_fields)
    assert registry.existing_cbr_case_model == "app.domain.cbr.CBRCase"
    assert registry.existing_cbr_loader == "app.services.cbr_loader.load_cbr_cases_jsonl"
    assert registry.existing_cbr_anonymizer == "app.services.cbr_anonymizer.anonymize_text"
    assert registry.operational_cases == []
    assert not registry.persists_operational_cases
    assert not registry.modifies_existing_cbr_engine
    assert not registry.can_control_legal_decision


def test_c10_blocker_counts_explain_why_zero_cases_are_operational() -> None:
    registry = _load_registry()

    assert registry.operational_blocker_counts == {
        "corpus_not_validated": 17,
        "required_case_fields_missing": 30,
        "temporal_validation_pending": 37,
        "resolution_outcome_not_verified": 37,
        "anonymization_review_pending": 37,
    }
    assert all(item.operational_blockers for item in registry.assessments)
    assert not any(item.operational_case_created for item in registry.assessments)


def test_c10_is_reproducible_from_c6_c7_and_c9() -> None:
    registry = _load_registry()
    c6 = load_primary_cbr_normative_citation_linkage(
        RESOURCES / "primary_cbr_normative_citations.json"
    )
    c7 = load_primary_cbr_corpus_validation_report(
        RESOURCES / "primary_cbr_corpus_validation.json"
    )
    c9 = load_primary_cbr_legal_similarity_index(
        RESOURCES / "primary_cbr_legal_similarity.json"
    )

    validate_primary_cbr_level_registry(registry, c6, c7, c9)
