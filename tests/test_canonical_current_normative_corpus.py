from datetime import date, timedelta

from app.domain.normative import (
    NormativeApplicabilityRequest,
    NormativeDecision,
)
from app.services.normative_engine import evaluate_normative_applicability


def test_current_canonical_normative_without_temporal_metadata_is_applicable() -> None:
    today = date.today()

    result = evaluate_normative_applicability(
        NormativeApplicabilityRequest(
            legal_unit_id=1,
            document_id="cff",
            version_label="canonical",
            query_date=today,
        )
    )

    assert result.decision is NormativeDecision.APPLICABLE
    assert result.applicable is True
    assert result.requires_human_review is False


def test_noncanonical_source_does_not_receive_canonical_exception() -> None:
    today = date.today()

    result = evaluate_normative_applicability(
        NormativeApplicabilityRequest(
            legal_unit_id=1,
            document_id="external",
            version_label="external",
            query_date=today,
        )
    )

    assert result.decision is NormativeDecision.UNKNOWN_VALIDITY
    assert result.applicable is False
    assert result.requires_human_review is True


def test_historical_query_without_temporal_evidence_remains_fail_closed() -> None:
    today = date.today()

    result = evaluate_normative_applicability(
        NormativeApplicabilityRequest(
            legal_unit_id=1,
            document_id="cff",
            version_label="canonical",
            query_date=today - timedelta(days=1),
        )
    )

    assert result.decision is NormativeDecision.UNKNOWN_VALIDITY
    assert result.applicable is False
    assert result.requires_human_review is True


def test_explicit_future_effective_date_is_respected_for_canonical_source() -> None:
    today = date.today()

    result = evaluate_normative_applicability(
        NormativeApplicabilityRequest(
            legal_unit_id=1,
            document_id="lieps",
            version_label="canonical",
            effective_from=today + timedelta(days=1),
            query_date=today,
        )
    )

    assert result.decision is NormativeDecision.NOT_YET_EFFECTIVE
    assert result.applicable is False
