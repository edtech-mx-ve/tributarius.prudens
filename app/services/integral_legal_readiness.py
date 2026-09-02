from __future__ import annotations

from app.domain.integral_legal_readiness import (
    EvidentiarySufficiency,
    LegalAnalysisReadiness,
    LegalCompletenessDimension,
    LegalCompletenessItem,
    LegalCompletenessState,
)
from app.domain.orchestration import HybridOrchestrationResult
from app.domain.query import QueryIntent


def _facts_item(result: HybridOrchestrationResult) -> LegalCompletenessItem:
    facts = result.analysis.facts
    has_gaps = bool(
        result.analysis.missing_fields
        or result.analysis.ambiguities
        or result.analysis.requires_clarification
    )
    if not facts:
        return LegalCompletenessItem(
            dimension=LegalCompletenessDimension.FACTS,
            state=LegalCompletenessState.MISSING,
            reason="No hay hechos jurídicamente utilizables identificados.",
        )
    if has_gaps:
        return LegalCompletenessItem(
            dimension=LegalCompletenessDimension.FACTS,
            state=LegalCompletenessState.PARTIAL,
            reason="Existen hechos identificados, pero persisten faltantes o ambigüedades.",
        )
    return LegalCompletenessItem(
        dimension=LegalCompletenessDimension.FACTS,
        state=LegalCompletenessState.COMPLETE,
        reason="Los hechos identificados no presentan faltantes declarados.",
    )


def _normative_item(result: HybridOrchestrationResult) -> LegalCompletenessItem:
    refs = list(result.applicable_normative_refs)
    if not refs:
        return LegalCompletenessItem(
            dimension=LegalCompletenessDimension.NORMATIVE_BASIS,
            state=LegalCompletenessState.MISSING,
            reason="No existe referencia normativa aplicable confirmada.",
        )
    return LegalCompletenessItem(
        dimension=LegalCompletenessDimension.NORMATIVE_BASIS,
        state=LegalCompletenessState.COMPLETE,
        reason="Existe fundamento normativo aplicable identificado.",
        evidence_refs=refs,
    )


def _rule_item(result: HybridOrchestrationResult) -> LegalCompletenessItem:
    conclusions = result.rule_result.matched_rules
    if not conclusions:
        return LegalCompletenessItem(
            dimension=LegalCompletenessDimension.RULE_REASONING,
            state=LegalCompletenessState.MISSING,
            reason="El RBS no produjo una conclusión aplicable.",
        )

    refs = [
        ref
        for conclusion in conclusions
        for ref in conclusion.normative_refs
    ]
    return LegalCompletenessItem(
        dimension=LegalCompletenessDimension.RULE_REASONING,
        state=LegalCompletenessState.COMPLETE,
        reason="El RBS produjo al menos una conclusión jurídica trazable.",
        evidence_refs=list(dict.fromkeys(refs)),
    )


def _calculation_item(result: HybridOrchestrationResult) -> LegalCompletenessItem:
    if result.analysis.primary_intent != QueryIntent.CALCULATE_ISR:
        return LegalCompletenessItem(
            dimension=LegalCompletenessDimension.CALCULATION,
            state=LegalCompletenessState.NOT_APPLICABLE,
            reason="La consulta no exige un cálculo ISR como resultado principal.",
        )

    if result.isr_result is None:
        return LegalCompletenessItem(
            dimension=LegalCompletenessDimension.CALCULATION,
            state=LegalCompletenessState.MISSING,
            reason="La consulta exige cálculo ISR, pero no existe resultado calculado.",
        )

    return LegalCompletenessItem(
        dimension=LegalCompletenessDimension.CALCULATION,
        state=LegalCompletenessState.COMPLETE,
        reason="El cálculo ISR requerido fue producido con referencia normativa.",
        evidence_refs=[result.isr_result.normative_ref],
    )


def _missing_requirements(
    result: HybridOrchestrationResult,
    completeness: list[LegalCompletenessItem],
) -> list[str]:
    requirements = [
        f"{field.name}: {field.reason}"
        for field in result.analysis.missing_fields
    ]
    requirements.extend(result.analysis.ambiguities)

    for item in completeness:
        if item.state == LegalCompletenessState.MISSING:
            requirements.append(f"{item.dimension.value}: {item.reason}")

    return list(dict.fromkeys(requirements))


def _has_evidence_insufficiency_signal(result: HybridOrchestrationResult) -> bool:
    evaluation = result.heuristic_evaluation
    if evaluation is None:
        return False
    return any(signal.code == "HEUR-EVID-001" for signal in evaluation.signals)


def _sufficiency(
    result: HybridOrchestrationResult,
    completeness: list[LegalCompletenessItem],
) -> EvidentiarySufficiency:
    essential_missing = any(
        item.state == LegalCompletenessState.MISSING
        for item in completeness
        if item.dimension
        in {
            LegalCompletenessDimension.FACTS,
            LegalCompletenessDimension.NORMATIVE_BASIS,
            LegalCompletenessDimension.RULE_REASONING,
            LegalCompletenessDimension.CALCULATION,
        }
    )
    if essential_missing or _has_evidence_insufficiency_signal(result):
        return EvidentiarySufficiency.INSUFFICIENT

    if (
        result.analysis.missing_fields
        or result.analysis.ambiguities
        or result.analysis.requires_clarification
        or result.requires_human_review
    ):
        return EvidentiarySufficiency.LIMITED

    return EvidentiarySufficiency.SUFFICIENT


def evaluate_integral_legal_readiness(
    result: HybridOrchestrationResult,
) -> LegalAnalysisReadiness:
    """Evalúa completitud sin modificar ninguna conclusión jurídica existente."""

    completeness = [
        _facts_item(result),
        _normative_item(result),
        _rule_item(result),
        _calculation_item(result),
    ]
    sufficiency = _sufficiency(result, completeness)
    requires_clarification = result.analysis.requires_clarification

    return LegalAnalysisReadiness(
        completeness=completeness,
        missing_requirements=_missing_requirements(result, completeness),
        evidentiary_sufficiency=sufficiency,
        can_close_automatically=(
            sufficiency == EvidentiarySufficiency.SUFFICIENT
            and not requires_clarification
            and not result.requires_human_review
        ),
        requires_clarification=requires_clarification,
        requires_human_review=result.requires_human_review,
    )
