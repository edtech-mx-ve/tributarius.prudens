import pytest

from app.domain.cbr import (
    CaseStatus,
    CBRCase,
    CBRQuery,
    CBRReuseDecision,
)
from app.services.cbr_reasoning import assess_case_reuse
from app.services.cbr_traceability import (
    CBRTraceabilityError,
    build_cbr_reasoning_trace,
)
from cbr.engine import retrieve_similar_cases


def query() -> CBRQuery:
    return CBRQuery(
        taxpayer_type="individual",
        activity="servicios profesionales",
        tax="ISR",
        problem_type="determinacion de obligaciones",
        procedural_stage="orientacion",
        fiscal_year=2026,
    )


def case(
    *,
    case_id: str,
    normative_refs: list[str] | None = None,
    activity: str = "servicios profesionales",
    procedural_stage: str = "orientacion",
) -> CBRCase:
    return CBRCase(
        case_id=case_id,
        status=CaseStatus.ACTIVE,
        taxpayer_type="individual",
        activity=activity,
        tax="ISR",
        problem_type="determinacion de obligaciones",
        procedural_stage=procedural_stage,
        fiscal_year=2026,
        resolution_summary="Caso fiscal sintético.",
        normative_refs=(
            ["NORM_TEST_ISR_2026"]
            if normative_refs is None
            else normative_refs
        ),
        source_refs=[f"SOURCE-{case_id}"],
    )


def test_trace_preserves_retrieval_and_reuse_evidence() -> None:
    retrieval = retrieve_similar_cases(
        query(),
        [case(case_id="CASE-TRACE-001")],
    )
    assessments = [
        assess_case_reuse(
            item,
            current_normative_refs={"NORM_TEST_ISR_2026"},
        )
        for item in retrieval.matches
    ]

    trace = build_cbr_reasoning_trace(retrieval, assessments)

    assert trace.candidate_count == retrieval.candidate_count
    assert trace.returned_count == 1
    assert trace.requires_human_review is False

    item = trace.cases[0]
    assert item.case_id == "CASE-TRACE-001"
    assert item.rank == 1
    assert item.similarity == retrieval.matches[0].similarity
    assert item.reuse_decision == CBRReuseDecision.ELIGIBLE
    assert item.normative_refs == ["NORM_TEST_ISR_2026"]
    assert item.shared_normative_refs == ["NORM_TEST_ISR_2026"]
    assert item.source_refs == ["SOURCE-CASE-TRACE-001"]
    assert item.field_scores == retrieval.matches[0].field_scores


def test_trace_exposes_review_reason_without_rewriting_normative_refs() -> None:
    retrieval = retrieve_similar_cases(
        query(),
        [
            case(
                case_id="CASE-TRACE-OTHER-NORM",
                normative_refs=["NORM_OTHER"],
            )
        ],
    )
    assessments = [
        assess_case_reuse(
            item,
            current_normative_refs={"NORM_TEST_ISR_2026"},
        )
        for item in retrieval.matches
    ]

    trace = build_cbr_reasoning_trace(retrieval, assessments)

    item = trace.cases[0]
    assert item.reuse_decision == CBRReuseDecision.REVIEW_REQUIRED
    assert item.requires_human_review is True
    assert trace.requires_human_review is True
    assert item.normative_refs == ["NORM_OTHER"]
    assert item.shared_normative_refs == []
    assert "No hay referencia normativa compartida" in item.reuse_reason


def test_trace_preserves_deterministic_ranking() -> None:
    retrieval = retrieve_similar_cases(
        query(),
        [
            case(case_id="CASE-TRACE-B"),
            case(case_id="CASE-TRACE-A"),
        ],
    )
    assessments = [
        assess_case_reuse(
            item,
            current_normative_refs={"NORM_TEST_ISR_2026"},
        )
        for item in retrieval.matches
    ]

    trace = build_cbr_reasoning_trace(retrieval, assessments)

    assert [item.case_id for item in trace.cases] == [
        "CASE-TRACE-A",
        "CASE-TRACE-B",
    ]
    assert [item.rank for item in trace.cases] == [1, 2]


def test_trace_rejects_missing_assessment() -> None:
    retrieval = retrieve_similar_cases(
        query(),
        [case(case_id="CASE-TRACE-001")],
    )

    with pytest.raises(CBRTraceabilityError, match="desalineadas"):
        build_cbr_reasoning_trace(retrieval, [])


def test_trace_rejects_assessment_for_different_case() -> None:
    retrieval = retrieve_similar_cases(
        query(),
        [case(case_id="CASE-TRACE-001")],
    )
    other_retrieval = retrieve_similar_cases(
        query(),
        [case(case_id="CASE-TRACE-002")],
    )
    wrong = [
        assess_case_reuse(
            other_retrieval.matches[0],
            current_normative_refs={"NORM_TEST_ISR_2026"},
        )
    ]

    with pytest.raises(CBRTraceabilityError, match="desalineadas"):
        build_cbr_reasoning_trace(retrieval, wrong)


def test_trace_of_empty_retrieval_is_valid_and_needs_no_review() -> None:
    retrieval = retrieve_similar_cases(
        query(),
        [
            case(
                case_id="CASE-TRACE-NONMATCH",
                activity="comercio exterior",
                procedural_stage="fiscalizacion",
            )
        ],
    )

    # Force rejection at retrieval by changing a critical field.
    nonmatching = case(case_id="CASE-TRACE-NONMATCH")
    nonmatching.tax = "IVA"
    retrieval = retrieve_similar_cases(query(), [nonmatching])

    trace = build_cbr_reasoning_trace(retrieval, [])

    assert trace.returned_count == 0
    assert trace.cases == []
    assert trace.requires_human_review is False
