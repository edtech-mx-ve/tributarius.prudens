from app.domain.cbr import CaseStatus, CBRCase, CBRQuery
from cbr.similarity import case_similarity, fiscal_year_similarity, jaccard_similarity


def make_case() -> CBRCase:
    return CBRCase(
        case_id="CASE-001",
        status=CaseStatus.ACTIVE,
        taxpayer_type="individual",
        activity="servicios profesionales",
        tax="ISR",
        problem_type="determinacion de obligaciones",
        authority_act=None,
        procedural_stage="orientacion",
        fiscal_year=2026,
        resolution_summary="Caso de prueba.",
        normative_refs=["NORM_TEST_ISR_2026"],
        source_refs=["SRC"],
    )


def make_query() -> CBRQuery:
    return CBRQuery(
        taxpayer_type="individual",
        activity="servicios profesionales",
        tax="ISR",
        problem_type="determinacion de obligaciones",
        authority_act=None,
        procedural_stage="orientacion",
        fiscal_year=2026,
    )


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
