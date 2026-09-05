from app.domain.cbr import (
    CaseField,
    CaseStatus,
    CBRMatch,
    CBRQuery,
    CBRRetrievalResult,
    CBRReuseAssessment,
    CBRReuseDecision,
    FieldSimilarity,
)
from app.services.hybrid_reasoning_normalization import (
    normalize_cbr_result,
)


def _field(
    field: CaseField,
    score: float,
    weight: float,
    query_value: str,
    case_value: str,
) -> FieldSimilarity:
    return FieldSimilarity(
        field=field,
        score=score,
        weight=weight,
        query_value=query_value,
        case_value=case_value,
    )


def _result(
    *,
    activity_score: float = 1.0,
) -> CBRRetrievalResult:
    query = CBRQuery(
        taxpayer_type="individual",
        activity="servicios profesionales independientes",
        tax="ISR",
        problem_type="cumplimiento_fiscal",
        authority_act=None,
        procedural_stage=None,
        fiscal_year=2026,
        top_k=5,
    )

    match = CBRMatch(
        rank=1,
        case_id="CASE-TP-ISR-PROF-CUMPL-2026",
        status=CaseStatus.ACTIVE,
        similarity=1.0,
        resolution_summary="Caso canonico de cumplimiento fiscal.",
        normative_refs=[
            "lisr:articulo_100",
            "lisr:articulo_110",
        ],
        source_refs=[
            "RBS:ISR_PROFESSIONAL_CLASSIFY_001@1.0.0",
        ],
        field_scores=[
            _field(
                CaseField.TAXPAYER_TYPE,
                1.0,
                0.18,
                "individual",
                "individual",
            ),
            _field(
                CaseField.ACTIVITY,
                activity_score,
                0.16,
                "servicios profesionales independientes",
                "servicios profesionales independientes",
            ),
            _field(
                CaseField.TAX,
                1.0,
                0.18,
                "ISR",
                "ISR",
            ),
            _field(
                CaseField.PROBLEM_TYPE,
                1.0,
                0.18,
                "cumplimiento_fiscal",
                "cumplimiento_fiscal",
            ),
            _field(
                CaseField.AUTHORITY_ACT,
                0.0,
                0.0,
                "",
                "",
            ),
            _field(
                CaseField.PROCEDURAL_STAGE,
                0.0,
                0.0,
                "",
                "",
            ),
            _field(
                CaseField.FISCAL_YEAR,
                1.0,
                0.10,
                "2026",
                "2026",
            ),
        ],
        explanation="Caso comparable.",
        requires_human_review=False,
    )

    return CBRRetrievalResult(
        query=query,
        candidate_count=1,
        returned_count=1,
        matches=[match],
    )


def _assessment() -> CBRReuseAssessment:
    return CBRReuseAssessment(
        case_id="CASE-TP-ISR-PROF-CUMPL-2026",
        decision=CBRReuseDecision.ELIGIBLE,
        shared_normative_refs=[
            "lisr:articulo_100",
            "lisr:articulo_110",
        ],
        reason="Fundamento compartido.",
        requires_human_review=False,
    )


def test_zero_weight_optional_fields_are_not_conflicts() -> None:
    normalized = normalize_cbr_result(
        _result(),
        [_assessment()],
    )

    assert normalized.conflicting_facts == []
    assert normalized.requires_review is False


def test_real_weighted_difference_remains_conflict() -> None:
    normalized = normalize_cbr_result(
        _result(activity_score=0.5),
        [_assessment()],
    )

    assert any(
        item.startswith("activity:")
        for item in normalized.conflicting_facts
    )
