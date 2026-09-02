from __future__ import annotations

from app.domain.cbr import CBRRetrievalResult, CBRReuseAssessment, CBRReuseDecision
from app.domain.hybrid_reasoning import NormalizedReasoningResult, ReasoningSource
from app.domain.rules import RuleEvaluationResult


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def normalize_rbs_result(result: RuleEvaluationResult) -> NormalizedReasoningResult:
    """Adapta el motor de reglas existente al contrato híbrido común."""
    matched = result.matched_rules
    conclusions = [item.conclusion for item in matched]
    legal_basis = _unique([ref for item in matched for ref in item.normative_refs])
    references = _unique(
        legal_basis + [ref for item in matched for ref in item.source_refs]
    )
    uncertainty: list[str] = []
    if result.requires_human_review:
        uncertainty.append("El RBS requiere revisión humana.")

    trace = [
        f"{item.sequence}:{item.rule_id}@{item.version}:{item.conclusion_code}"
        for item in result.derivations
    ]
    if not trace:
        trace = [
            f"{item.rule_id}@{item.version}:{item.conclusion_code}"
            for item in matched
        ]

    return NormalizedReasoningResult(
        reasoning_source=ReasoningSource.RBS,
        conclusion="\n".join(conclusions) if conclusions else None,
        legal_basis=legal_basis,
        references=references,
        confidence=None,
        uncertainty=uncertainty,
        applicability=bool(matched),
        temporal_context=None,
        supporting_facts=_unique(
            [
                evidence.fact
                for derivation in result.derivations
                for evidence in derivation.conditions
            ]
        ),
        conflicting_facts=[],
        requires_review=result.requires_human_review,
        trace=trace,
    )


def normalize_cbr_result(
    result: CBRRetrievalResult | None,
    assessments: list[CBRReuseAssessment],
) -> NormalizedReasoningResult:
    """Adapta recuperación/reutilización CBR sin elevarla a norma jurídica."""
    if result is None:
        return NormalizedReasoningResult(
            reasoning_source=ReasoningSource.CBR,
            uncertainty=["No existe resultado CBR para normalizar."],
            applicability=None,
            requires_review=True,
            trace=["cbr:no_result"],
        )

    assessment_by_case = {item.case_id: item for item in assessments}
    eligible = [
        match
        for match in result.matches
        if (
            (assessment := assessment_by_case.get(match.case_id)) is not None
            and assessment.decision == CBRReuseDecision.ELIGIBLE
        )
    ]
    considered = eligible or result.matches
    best = considered[0] if considered else None

    legal_basis = _unique([ref for item in considered for ref in item.normative_refs])
    references = _unique(
        legal_basis + [ref for item in considered for ref in item.source_refs]
    )
    uncertainty = [
        item.reason
        for item in assessments
        if item.decision != CBRReuseDecision.ELIGIBLE
    ]
    if result.returned_count == 0:
        uncertainty.append("CBR no recuperó casos semejantes.")

    requires_review = (
        result.returned_count == 0
        or any(item.requires_human_review for item in assessments)
        or any(item.requires_human_review for item in result.matches)
    )
    applicability: bool | None
    if assessments:
        applicability = bool(eligible)
    elif result.matches:
        applicability = None
        uncertainty.append("Los casos recuperados no tienen evaluación de reutilización.")
        requires_review = True
    else:
        applicability = False

    return NormalizedReasoningResult(
        reasoning_source=ReasoningSource.CBR,
        conclusion=best.resolution_summary if best is not None else None,
        legal_basis=legal_basis,
        references=references,
        confidence=best.similarity if best is not None else None,
        uncertainty=_unique(uncertainty),
        applicability=applicability,
        temporal_context=(best.status.value if best is not None else None),
        supporting_facts=(
            [
                f"{score.field.value}={score.query_value}"
                for score in best.field_scores
                if score.score > 0
            ]
            if best is not None
            else []
        ),
        conflicting_facts=(
            [
                f"{score.field.value}: consulta={score.query_value}; caso={score.case_value}"
                for score in best.field_scores
                if score.score < 1
            ]
            if best is not None
            else []
        ),
        requires_review=requires_review,
        trace=[
            f"{match.rank}:{match.case_id}:similarity={match.similarity:.4f}"
            for match in result.matches
        ],
    )
