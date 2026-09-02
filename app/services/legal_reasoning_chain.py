from __future__ import annotations

from app.domain.legal_decision import LegalDecision
from app.domain.legal_reasoning_chain import (
    LegalReasoningChain,
    LegalReasoningStep,
    LegalReasoningStepKind,
)


def _allowed_evidence_refs(decision: LegalDecision) -> set[str]:
    refs: set[str] = set()
    for item in decision.evidence_map.items:
        refs.update(item.references)
    return refs


def _rule_evidence_refs(
    source_refs: list[str],
    allowed_refs: set[str],
) -> list[str]:
    """Conserva solo referencias que ya existen en el mapa integral de evidencia."""

    return [ref for ref in source_refs if ref in allowed_refs]


def build_legal_reasoning_chain(decision: LegalDecision) -> LegalReasoningChain:
    """Estructura el razonamiento existente sin completar enlaces no demostrados."""

    steps: list[LegalReasoningStep] = []
    allowed_evidence = _allowed_evidence_refs(decision)

    for conclusion in decision.rule_conclusions:
        steps.append(
            LegalReasoningStep(
                sequence=len(steps) + 1,
                kind=LegalReasoningStepKind.RULE_APPLICATION,
                fact_refs=[],
                normative_refs=[
                    ref
                    for ref in conclusion.normative_refs
                    if ref in decision.applicable_normative_refs
                ],
                rule_ref=f"{conclusion.rule_id}:{conclusion.version}",
                evidence_refs=_rule_evidence_refs(
                    conclusion.source_refs,
                    allowed_evidence,
                ),
                inference_code=conclusion.conclusion_code,
                conclusion=conclusion.conclusion,
                controlling_source="rbs",
                requires_human_review=conclusion.requires_human_review,
            )
        )

    if decision.conclusion is not None:
        steps.append(
            LegalReasoningStep(
                sequence=len(steps) + 1,
                kind=LegalReasoningStepKind.FINAL_DETERMINATION,
                normative_refs=list(decision.applicable_normative_refs),
                conclusion=decision.conclusion,
                controlling_source=decision.controlling_source,
                requires_human_review=decision.requires_human_review,
            )
        )

    return LegalReasoningChain(steps=steps)
