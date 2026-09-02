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
from app.domain.hybrid_reasoning import ReasoningSource
from app.domain.rules import RuleConclusion, RuleEvaluationResult
from app.services.hybrid_reasoning_normalization import (
    normalize_cbr_result,
    normalize_rbs_result,
)


def test_rbs_normalization_preserves_conclusion_basis_review_and_trace() -> None:
    result = RuleEvaluationResult(
        matched_rules=[
            RuleConclusion(
                rule_id="ISR_RULE_001",
                version="1.0",
                conclusion_code="isr_obligation",
                conclusion="Existe obligación de revisar ISR.",
                normative_refs=["LISR:ART-1"],
                source_refs=["SRC-LISR-1"],
                requires_human_review=True,
            )
        ],
        traces=[],
        requires_human_review=True,
    )

    normalized = normalize_rbs_result(result)

    assert normalized.reasoning_source == ReasoningSource.RBS
    assert normalized.conclusion == "Existe obligación de revisar ISR."
    assert normalized.legal_basis == ["LISR:ART-1"]
    assert normalized.references == ["LISR:ART-1", "SRC-LISR-1"]
    assert normalized.confidence is None
    assert normalized.applicability is True
    assert normalized.requires_review is True
    assert normalized.uncertainty == ["El RBS requiere revisión humana."]
    assert normalized.trace == ["ISR_RULE_001@1.0:isr_obligation"]


def _cbr_result() -> CBRRetrievalResult:
    return CBRRetrievalResult(
        query=CBRQuery(
            taxpayer_type="individual",
            activity="servicios",
            tax="ISR",
            problem_type="obligacion",
            fiscal_year=2026,
        ),
        candidate_count=1,
        returned_count=1,
        matches=[
            CBRMatch(
                rank=1,
                case_id="CASE-ISR-001",
                status=CaseStatus.ACTIVE,
                similarity=0.91,
                resolution_summary="Caso semejante confirmó la obligación.",
                normative_refs=["LISR:ART-1"],
                source_refs=["CASE-SOURCE-1"],
                field_scores=[
                    FieldSimilarity(
                        field=CaseField.TAX,
                        score=1.0,
                        weight=0.2,
                        query_value="ISR",
                        case_value="ISR",
                    ),
                    FieldSimilarity(
                        field=CaseField.ACTIVITY,
                        score=0.5,
                        weight=0.1,
                        query_value="servicios",
                        case_value="comercio",
                    ),
                ],
                explanation="Caso semejante por impuesto y problema.",
                requires_human_review=False,
            )
        ],
    )


def test_cbr_normalization_preserves_experience_similarity_and_differences() -> None:
    assessment = CBRReuseAssessment(
        case_id="CASE-ISR-001",
        decision=CBRReuseDecision.ELIGIBLE,
        shared_normative_refs=["LISR:ART-1"],
        reason="Caso compatible.",
        requires_human_review=False,
    )

    normalized = normalize_cbr_result(_cbr_result(), [assessment])

    assert normalized.reasoning_source == ReasoningSource.CBR
    assert normalized.conclusion == "Caso semejante confirmó la obligación."
    assert normalized.legal_basis == ["LISR:ART-1"]
    assert normalized.references == ["LISR:ART-1", "CASE-SOURCE-1"]
    assert normalized.confidence == 0.91
    assert normalized.applicability is True
    assert normalized.temporal_context == "active"
    assert normalized.requires_review is False
    assert normalized.supporting_facts == ["tax=ISR", "activity=servicios"]
    assert normalized.conflicting_facts == [
        "activity: consulta=servicios; caso=comercio"
    ]
    assert normalized.trace == ["1:CASE-ISR-001:similarity=0.9100"]


def test_cbr_rejected_case_exposes_uncertainty_and_review() -> None:
    assessment = CBRReuseAssessment(
        case_id="CASE-ISR-001",
        decision=CBRReuseDecision.REJECTED,
        shared_normative_refs=[],
        reason="La similitud es insuficiente.",
        requires_human_review=True,
    )

    normalized = normalize_cbr_result(_cbr_result(), [assessment])

    assert normalized.reasoning_source == ReasoningSource.CBR
    assert normalized.applicability is False
    assert normalized.requires_review is True
    assert "La similitud es insuficiente." in normalized.uncertainty


def test_missing_cbr_result_is_explicit_and_safe() -> None:
    normalized = normalize_cbr_result(None, [])

    assert normalized.reasoning_source == ReasoningSource.CBR
    assert normalized.conclusion is None
    assert normalized.applicability is None
    assert normalized.requires_review is True
    assert normalized.trace == ["cbr:no_result"]
