from __future__ import annotations

from app.domain.cbr import CBRRetrievalResult, CBRReuseAssessment
from app.domain.cbr_trace import CBRCaseReasoningTrace, CBRReasoningTrace


class CBRTraceabilityError(ValueError):
    """Inconsistencia entre recuperación CBR y evaluación de reutilización."""


def build_cbr_reasoning_trace(
    retrieval: CBRRetrievalResult,
    assessments: list[CBRReuseAssessment],
) -> CBRReasoningTrace:
    """Construye una traza determinista y auditable del razonamiento CBR."""
    assessment_by_case = {item.case_id: item for item in assessments}

    if len(assessment_by_case) != len(assessments):
        raise CBRTraceabilityError(
            "Las evaluaciones CBR contienen case_id duplicados."
        )

    match_ids = {item.case_id for item in retrieval.matches}
    assessment_ids = set(assessment_by_case)

    if match_ids != assessment_ids:
        missing = sorted(match_ids - assessment_ids)
        unexpected = sorted(assessment_ids - match_ids)
        raise CBRTraceabilityError(
            "La traza CBR no puede construirse con evaluaciones desalineadas: "
            f"missing={missing}; unexpected={unexpected}."
        )

    cases: list[CBRCaseReasoningTrace] = []
    for match in retrieval.matches:
        assessment = assessment_by_case[match.case_id]
        cases.append(
            CBRCaseReasoningTrace(
                rank=match.rank,
                case_id=match.case_id,
                status=match.status,
                similarity=match.similarity,
                field_scores=match.field_scores,
                normative_refs=list(match.normative_refs),
                source_refs=list(match.source_refs),
                reuse_decision=assessment.decision,
                reuse_reason=assessment.reason,
                shared_normative_refs=list(assessment.shared_normative_refs),
                requires_human_review=assessment.requires_human_review,
            )
        )

    return CBRReasoningTrace(
        query=retrieval.query,
        candidate_count=retrieval.candidate_count,
        returned_count=retrieval.returned_count,
        cases=cases,
        requires_human_review=any(
            item.requires_human_review for item in cases
        ),
    )
