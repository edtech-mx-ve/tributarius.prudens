from __future__ import annotations

from app.domain.legal_consequences import (
    LegalConsequence,
    LegalConsequenceKind,
    LegalConsequences,
    LegalConsequenceStatus,
)
from app.domain.legal_decision import LegalDecision


def _allowed_evidence_refs(decision: LegalDecision) -> set[str]:
    refs: set[str] = set()
    for item in decision.evidence_map.items:
        refs.update(item.references)
    return refs


def build_legal_consequences(decision: LegalDecision) -> LegalConsequences:
    """Proyecta efectos explícitos ya contenidos en las conclusiones de reglas."""

    allowed_evidence = _allowed_evidence_refs(decision)
    items: list[LegalConsequence] = []

    for rule in decision.rule_conclusions:
        normalized = rule.conclusion_code.casefold()

        if normalized.startswith("obligation_"):
            kind = LegalConsequenceKind.OBLIGATION
        elif normalized.startswith("right_"):
            kind = LegalConsequenceKind.RIGHT
        elif normalized.startswith("action_"):
            kind = LegalConsequenceKind.ACTION
        elif normalized.startswith("risk_"):
            kind = LegalConsequenceKind.RISK
        elif normalized.startswith("deadline_"):
            kind = LegalConsequenceKind.DEADLINE
        else:
            continue

        status = (
            LegalConsequenceStatus.CONDITIONAL
            if decision.requires_human_review or decision.missing_fields
            else LegalConsequenceStatus.DETERMINED
        )

        items.append(
            LegalConsequence(
                kind=kind,
                status=status,
                description=rule.conclusion,
                normative_refs=[
                    ref
                    for ref in rule.normative_refs
                    if ref in decision.applicable_normative_refs
                ],
                evidence_refs=[
                    ref for ref in rule.source_refs if ref in allowed_evidence
                ],
                source_rule_refs=[f"{rule.rule_id}:{rule.version}"],
                requires_human_review=(
                    rule.requires_human_review or decision.requires_human_review
                ),
            )
        )

    return LegalConsequences(items=items)
