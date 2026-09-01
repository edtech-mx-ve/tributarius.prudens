from app.domain.cbr import CaseStatus, CBRCase, CBRQuery
from cbr.engine import MINIMUM_CBR_SIMILARITY, retrieve_similar_cases


def case(
    case_id: str,
    status: CaseStatus,
    tax: str = "ISR",
    *,
    taxpayer_type: str = "individual",
    activity: str = "servicios profesionales",
    problem_type: str = "determinacion de obligaciones",
) -> CBRCase:
    return CBRCase(
        case_id=case_id,
        status=status,
        taxpayer_type=taxpayer_type,
        activity=activity,
        tax=tax,
        problem_type=problem_type,
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


def test_minimum_similarity_is_explicit_and_conservative() -> None:
    assert MINIMUM_CBR_SIMILARITY == 0.60


def test_different_tax_is_rejected_even_if_other_fields_match() -> None:
    result = retrieve_similar_cases(
        query(),
        [case("CASE-IVA", CaseStatus.ACTIVE, tax="IVA")],
    )
    assert result.candidate_count == 1
    assert result.returned_count == 0
    assert result.matches == []


def test_different_taxpayer_type_is_rejected() -> None:
    result = retrieve_similar_cases(
        query(),
        [
            case(
                "CASE-CORP",
                CaseStatus.ACTIVE,
                taxpayer_type="legal_entity",
            )
        ],
    )
    assert result.returned_count == 0


def test_different_problem_type_is_rejected() -> None:
    result = retrieve_similar_cases(
        query(),
        [
            case(
                "CASE-AUDIT",
                CaseStatus.ACTIVE,
                problem_type="procedimiento de fiscalizacion",
            )
        ],
    )
    assert result.returned_count == 0


def test_weak_activity_similarity_does_not_block_critical_match() -> None:
    result = retrieve_similar_cases(
        query(),
        [
            case(
                "CASE-OTHER-ACTIVITY",
                CaseStatus.ACTIVE,
                activity="consultoria tecnologica especializada",
            )
        ],
    )
    assert result.returned_count == 1
    assert result.matches[0].similarity >= MINIMUM_CBR_SIMILARITY
