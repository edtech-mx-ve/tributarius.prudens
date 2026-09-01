from datetime import date

from app.domain.normative import (
    NormativeDecision,
    NormativeSelectionRequest,
    NormativeVersionView,
)
from app.services.normative_engine import evaluate_normative_versions


def test_unknown_validity_is_preserved_as_normative_evidence() -> None:
    result = evaluate_normative_versions(
        NormativeSelectionRequest(
            legal_unit_id=27,
            query_date=date(2026, 8, 31),
            query_fiscal_year=2026,
        ),
        [NormativeVersionView(version_label="CFF-foundational")],
    )[0]

    assert result.decision == NormativeDecision.UNKNOWN_VALIDITY
    assert result.applicable is False
    assert result.evidence_available is True
    assert result.requires_human_review is True


def test_expired_version_remains_evidence_but_is_not_applicable() -> None:
    result = evaluate_normative_versions(
        NormativeSelectionRequest(
            legal_unit_id=27,
            query_date=date(2026, 8, 31),
            query_fiscal_year=2026,
        ),
        [
            NormativeVersionView(
                version_label="historical",
                effective_from=date(2025, 1, 1),
                effective_to=date(2025, 12, 31),
            )
        ],
    )[0]

    assert result.decision == NormativeDecision.EXPIRED
    assert result.applicable is False
    assert result.evidence_available is True


def test_unknown_and_applicable_versions_are_both_evaluated() -> None:
    results = evaluate_normative_versions(
        NormativeSelectionRequest(
            legal_unit_id=27,
            query_date=date(2026, 8, 31),
            query_fiscal_year=2026,
        ),
        [
            NormativeVersionView(version_label="unknown"),
            NormativeVersionView(
                version_label="2026",
                effective_from=date(2026, 1, 1),
                effective_to=date(2026, 12, 31),
                fiscal_year=2026,
            ),
        ],
    )

    assert [result.version_label for result in results] == ["unknown", "2026"]
    assert results[0].decision == NormativeDecision.UNKNOWN_VALIDITY
    assert results[0].evidence_available is True
    assert results[1].decision == NormativeDecision.APPLICABLE
    assert results[1].applicable is True
