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


def test_verified_permanent_norm_is_applicable_only_for_verified_snapshot() -> None:
    from app.domain.normative import (
        NormativeValidityBasis,
        NormativeValidityScope,
        NormativeValidityStatus,
    )

    result = evaluate_normative_applicability(
        NormativeApplicabilityRequest(
            legal_unit_id=27,
            version_label="CFF-2026-04-09",
            validity_status=NormativeValidityStatus.VERIFIED_IN_FORCE,
            validity_scope=NormativeValidityScope.DOCUMENT,
            validity_basis=NormativeValidityBasis.OFFICIAL_CONSOLIDATED_VERSION,
            validity_verified_at=date(2026, 8, 30),
            official_source="https://www.diputados.gob.mx/LeyesBiblio/pdf/CFF.pdf",
            query_date=date(2026, 8, 30),
            query_fiscal_year=2026,
        )
    )

    assert result.applicable is True
    assert result.decision == NormativeDecision.APPLICABLE
    assert result.requires_human_review is False


def test_verified_snapshot_does_not_backfill_unknown_historical_validity() -> None:
    from app.domain.normative import (
        NormativeValidityBasis,
        NormativeValidityScope,
        NormativeValidityStatus,
    )

    result = evaluate_normative_applicability(
        NormativeApplicabilityRequest(
            legal_unit_id=27,
            version_label="CFF-2026-04-09",
            validity_status=NormativeValidityStatus.VERIFIED_IN_FORCE,
            validity_scope=NormativeValidityScope.DOCUMENT,
            validity_basis=NormativeValidityBasis.OFFICIAL_CONSOLIDATED_VERSION,
            validity_verified_at=date(2026, 8, 30),
            official_source="https://www.diputados.gob.mx/LeyesBiblio/pdf/CFF.pdf",
            query_date=date(2026, 7, 1),
            query_fiscal_year=2026,
        )
    )

    assert result.applicable is False
    assert result.decision == NormativeDecision.UNKNOWN_VALIDITY
    assert result.requires_human_review is True


def test_conflicting_temporal_metadata_is_invalid_and_requires_review() -> None:
    from app.domain.normative import NormativeValidityStatus

    result = evaluate_normative_applicability(
        NormativeApplicabilityRequest(
            legal_unit_id=1,
            version_label="conflicting",
            effective_from=date(2026, 1, 1),
            validity_status=NormativeValidityStatus.CONFLICTING,
            query_date=date(2026, 8, 30),
        )
    )

    assert result.applicable is False
    assert result.decision == NormativeDecision.INVALID_DATA
    assert result.requires_human_review is True


def test_permanent_norm_with_null_fiscal_year_can_be_applicable() -> None:
    from app.domain.normative import (
        NormativeValidityBasis,
        NormativeValidityScope,
        NormativeValidityStatus,
    )

    result = evaluate_normative_applicability(
        NormativeApplicabilityRequest(
            legal_unit_id=2,
            version_label="permanent",
            fiscal_year=None,
            validity_status=NormativeValidityStatus.VERIFIED_IN_FORCE,
            validity_scope=NormativeValidityScope.LEGAL_UNIT,
            validity_basis=NormativeValidityBasis.VERIFIED_REFORM_CHAIN,
            validity_verified_at=date(2026, 8, 30),
            official_source="official://verified-source",
            query_date=date(2026, 8, 30),
            query_fiscal_year=2026,
        )
    )
    assert result.applicable is True
