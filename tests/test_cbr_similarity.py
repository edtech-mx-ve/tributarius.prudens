import pytest

from app.domain.cbr import CaseField, CaseStatus, CBRCase, CBRQuery
from cbr.similarity import (
    FIELD_WEIGHTS,
    case_similarity,
    explain_similarity,
    fiscal_year_similarity,
    jaccard_similarity,
)


def make_case(
    *,
    fiscal_year: int = 2026,
    authority_act: str | None = None,
    procedural_stage: str | None = "orientacion",
) -> CBRCase:
    return CBRCase(
        case_id="CASE-001",
        status=CaseStatus.ACTIVE,
        taxpayer_type="individual",
        activity="servicios profesionales",
        tax="ISR",
        problem_type="determinacion de obligaciones",
        authority_act=authority_act,
        procedural_stage=procedural_stage,
        fiscal_year=fiscal_year,
        resolution_summary="Caso de prueba.",
        normative_refs=["NORM_TEST_ISR_2026"],
        source_refs=["SRC"],
    )


def make_query(
    *,
    fiscal_year: int = 2026,
    authority_act: str | None = None,
    procedural_stage: str | None = "orientacion",
) -> CBRQuery:
    return CBRQuery(
        taxpayer_type="individual",
        activity="servicios profesionales",
        tax="ISR",
        problem_type="determinacion de obligaciones",
        authority_act=authority_act,
        procedural_stage=procedural_stage,
        fiscal_year=fiscal_year,
    )


def test_field_weights_are_explicit_and_sum_to_one() -> None:
    assert set(FIELD_WEIGHTS) == set(CaseField)
    assert sum(FIELD_WEIGHTS.values()) == pytest.approx(1.0)


def test_jaccard_is_accent_insensitive() -> None:
    assert jaccard_similarity("determinación fiscal", "determinacion fiscal") == 1.0


def test_fiscal_year_similarity_degrades_by_distance() -> None:
    assert fiscal_year_similarity(2026, 2026) == 1.0
    assert fiscal_year_similarity(2026, 2025) == 0.5
    assert fiscal_year_similarity(2026, 2024) == 0.0


def test_identical_case_has_full_similarity() -> None:
    similarity, fields = case_similarity(make_query(), make_case())
    assert similarity == 1.0
    assert len(fields) == 7


def test_missing_optional_fields_do_not_penalize_similarity() -> None:
    similarity, fields = case_similarity(
        make_query(authority_act=None, procedural_stage=None),
        make_case(authority_act=None, procedural_stage=None),
    )

    authority = next(
        item for item in fields if item.field == CaseField.AUTHORITY_ACT
    )
    stage = next(
        item for item in fields if item.field == CaseField.PROCEDURAL_STAGE
    )

    assert authority.weight == 0.0
    assert stage.weight == 0.0
    assert similarity == 1.0


def test_one_year_distance_has_controlled_penalty() -> None:
    similarity, fields = case_similarity(
        make_query(fiscal_year=2026),
        make_case(fiscal_year=2025),
    )
    fiscal = next(item for item in fields if item.field == CaseField.FISCAL_YEAR)

    assert fiscal.score == 0.5
    # authority_act is absent in both cases, so its 0.10 weight is excluded.
    # Effective denominator = 0.90; fiscal contribution = 0.05.
    assert similarity == pytest.approx(0.85 / 0.90)


def test_two_year_distance_has_full_fiscal_penalty() -> None:
    similarity, fields = case_similarity(
        make_query(fiscal_year=2026),
        make_case(fiscal_year=2024),
    )
    fiscal = next(item for item in fields if item.field == CaseField.FISCAL_YEAR)

    assert fiscal.score == 0.0
    # authority_act is absent in both cases, so effective denominator = 0.90.
    assert similarity == pytest.approx(0.80 / 0.90)


def test_explanation_reports_material_difference() -> None:
    _, fields = case_similarity(
        make_query(fiscal_year=2026),
        make_case(fiscal_year=2024),
    )
    explanation = explain_similarity(fields)

    assert "Coincidencias principales:" in explanation
    assert "Diferencias:" in explanation
    assert "fiscal_year" in explanation
