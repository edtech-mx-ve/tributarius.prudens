from datetime import date

from app.domain.normative import (
    NormativeApplicabilityRequest,
    NormativeDecision,
    NormativeSelectionRequest,
    NormativeVersionView,
)
from app.services.normative_engine import (
    evaluate_normative_applicability,
    select_applicable_versions,
)


def test_applicable_version() -> None:
    result = evaluate_normative_applicability(
        NormativeApplicabilityRequest(
            legal_unit_id=1,
            version_label="2026-A",
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 12, 31),
            fiscal_year=2026,
            query_date=date(2026, 8, 27),
            query_fiscal_year=2026,
        )
    )

    assert result.applicable is True
    assert result.decision == NormativeDecision.APPLICABLE


def test_not_yet_effective() -> None:
    result = evaluate_normative_applicability(
        NormativeApplicabilityRequest(
            legal_unit_id=1,
            version_label="future",
            effective_from=date(2027, 1, 1),
            query_date=date(2026, 8, 27),
        )
    )

    assert result.applicable is False
    assert result.decision == NormativeDecision.NOT_YET_EFFECTIVE


def test_expired_version() -> None:
    result = evaluate_normative_applicability(
        NormativeApplicabilityRequest(
            legal_unit_id=1,
            version_label="old",
            effective_from=date(2025, 1, 1),
            effective_to=date(2025, 12, 31),
            query_date=date(2026, 8, 27),
        )
    )

    assert result.applicable is False
    assert result.decision == NormativeDecision.EXPIRED


def test_fiscal_year_mismatch() -> None:
    result = evaluate_normative_applicability(
        NormativeApplicabilityRequest(
            legal_unit_id=1,
            version_label="2025",
            effective_from=date(2025, 1, 1),
            effective_to=date(2026, 12, 31),
            fiscal_year=2025,
            query_date=date(2026, 8, 27),
            query_fiscal_year=2026,
        )
    )

    assert result.applicable is False
    assert result.decision == NormativeDecision.FISCAL_YEAR_MISMATCH


def test_unknown_validity_requires_review() -> None:
    result = evaluate_normative_applicability(
        NormativeApplicabilityRequest(
            legal_unit_id=1,
            version_label="unknown",
            query_date=date(2026, 8, 27),
        )
    )

    assert result.applicable is False
    assert result.decision == NormativeDecision.UNKNOWN_VALIDITY
    assert result.requires_human_review is True


def test_select_only_applicable_versions() -> None:
    selected = select_applicable_versions(
        NormativeSelectionRequest(
            legal_unit_id=10,
            query_date=date(2026, 8, 27),
            query_fiscal_year=2026,
        ),
        [
            NormativeVersionView(
                version_label="2025",
                effective_from=date(2025, 1, 1),
                effective_to=date(2025, 12, 31),
                fiscal_year=2025,
            ),
            NormativeVersionView(
                version_label="2026",
                effective_from=date(2026, 1, 1),
                effective_to=date(2026, 12, 31),
                fiscal_year=2026,
            ),
        ],
    )

    assert [item.version_label for item in selected] == ["2026"]
