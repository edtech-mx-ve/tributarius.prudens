from app.domain.cbr import CaseStatus, CBRCase, CBRQuery
from cbr.engine import retrieve_similar_cases


def case(case_id: str, status: CaseStatus, tax: str = "ISR") -> CBRCase:
    return CBRCase(
        case_id=case_id,
        status=status,
        taxpayer_type="individual",
        activity="servicios profesionales",
        tax=tax,
        problem_type="determinacion de obligaciones",
        authority_act=None,
        procedural_stage="orientacion",
        fiscal_year=2026,
        resolution_summary="Caso sintético.",
        normative_refs=["NORM_TEST_ISR_2026"],
        source_refs=["SRC"],
    )


def query() -> CBRQuery:
    return CBRQuery(
        taxpayer_type="individual",
        activity="servicios profesionales",
        tax="ISR",
        problem_type="determinacion de obligaciones",
        authority_act=None,
        procedural_stage="orientacion",
        fiscal_year=2026,
        top_k=5,
    )


def test_retrieval_excludes_superseded_and_invalidated() -> None:
    result = retrieve_similar_cases(
        query(),
        [
            case("CASE-ACTIVE", CaseStatus.ACTIVE),
            case("CASE-HIST", CaseStatus.HISTORICAL),
            case("CASE-SUP", CaseStatus.SUPERSEDED),
            case("CASE-INV", CaseStatus.INVALIDATED),
        ],
    )
    ids = [item.case_id for item in result.matches]
    assert ids == ["CASE-ACTIVE", "CASE-HIST"]


def test_historical_case_requires_review() -> None:
    result = retrieve_similar_cases(
        query(),
        [case("CASE-HIST", CaseStatus.HISTORICAL)],
    )
    assert result.matches[0].requires_human_review is True


def test_ranking_is_deterministic() -> None:
    result = retrieve_similar_cases(
        query(),
        [
            case("CASE-B", CaseStatus.ACTIVE),
            case("CASE-A", CaseStatus.ACTIVE),
        ],
    )
    assert [item.case_id for item in result.matches] == ["CASE-A", "CASE-B"]
