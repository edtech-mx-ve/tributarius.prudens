from __future__ import annotations

from collections.abc import Mapping
from numbers import Real
from typing import Any

from app.domain.rules import (
    ConditionTrace,
    RuleConclusion,
    RuleCondition,
    RuleConditionEvidence,
    RuleDefinition,
    RuleDerivationTrace,
    RuleEvaluationResult,
    RuleFactOrigin,
    RuleOperator,
    RuleSet,
    RuleTrace,
)


class RuleEvaluationError(ValueError):
    """Error controlado de evaluación."""


def _is_number(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)


def evaluate_condition(
    condition: RuleCondition,
    facts: Mapping[str, Any],
) -> ConditionTrace:
    exists = condition.fact in facts
    actual = facts.get(condition.fact)
    expected = condition.value

    try:
        if condition.operator == RuleOperator.EXISTS:
            matched = exists is bool(expected)
        elif not exists:
            matched = False
        elif condition.operator == RuleOperator.EQ:
            matched = actual == expected
        elif condition.operator == RuleOperator.NE:
            matched = actual != expected
        elif condition.operator == RuleOperator.IN:
            matched = actual in expected
        elif condition.operator == RuleOperator.NOT_IN:
            matched = actual not in expected
        elif condition.operator in {
            RuleOperator.GT,
            RuleOperator.GTE,
            RuleOperator.LT,
            RuleOperator.LTE,
        }:
            if not _is_number(actual) or not _is_number(expected):
                matched = False
            elif condition.operator == RuleOperator.GT:
                matched = actual > expected
            elif condition.operator == RuleOperator.GTE:
                matched = actual >= expected
            elif condition.operator == RuleOperator.LT:
                matched = actual < expected
            else:
                matched = actual <= expected
        else:
            raise RuleEvaluationError(f"Operador no soportado: {condition.operator}")
    except TypeError as exc:
        raise RuleEvaluationError(
            f"Tipos incompatibles para el hecho '{condition.fact}'."
        ) from exc

    return ConditionTrace(
        fact=condition.fact,
        operator=condition.operator,
        expected=expected,
        actual=actual,
        matched=matched,
    )


def evaluate_rule(
    rule: RuleDefinition,
    facts: Mapping[str, Any],
    applicable_normative_refs: set[str] | None = None,
) -> tuple[RuleTrace, RuleConclusion | None]:
    if not rule.enabled:
        return RuleTrace(
            rule_id=rule.rule_id,
            version=rule.version,
            priority=rule.priority,
            matched=False,
            skipped_reason="Regla deshabilitada.",
        ), None

    if rule.normative_refs:
        if applicable_normative_refs is None:
            reason = "No se proporcionó evidencia de aplicabilidad normativa."
        elif set(rule.normative_refs) - applicable_normative_refs:
            reason = "Faltan referencias normativas aplicables."
        else:
            reason = None
        if reason is not None:
            return RuleTrace(
                rule_id=rule.rule_id,
                version=rule.version,
                priority=rule.priority,
                matched=False,
                skipped_reason=reason,
            ), None

    conditions = [evaluate_condition(item, facts) for item in rule.conditions]
    matched = all(item.matched for item in conditions)
    trace = RuleTrace(
        rule_id=rule.rule_id,
        version=rule.version,
        priority=rule.priority,
        matched=matched,
        conditions=conditions,
    )
    if not matched:
        return trace, None

    return trace, RuleConclusion(
        rule_id=rule.rule_id,
        version=rule.version,
        conclusion_code=rule.conclusion_code,
        conclusion=rule.conclusion,
        normative_refs=rule.normative_refs,
        source_refs=rule.source_refs,
        requires_human_review=rule.requires_human_review,
    )


def _ordered_rules(rule_set: RuleSet) -> list[RuleDefinition]:
    return sorted(
        rule_set.rules,
        key=lambda rule: (-rule.priority, rule.rule_id, rule.version),
    )


def _build_derivation(
    *,
    sequence: int,
    cycle: int,
    rule: RuleDefinition,
    trace: RuleTrace,
    conclusion: RuleConclusion,
    producers: Mapping[str, tuple[str, str] | None],
) -> RuleDerivationTrace:
    condition_evidence: list[RuleConditionEvidence] = []
    for condition in trace.conditions:
        producer = producers.get(condition.fact)
        condition_evidence.append(
            RuleConditionEvidence(
                fact=condition.fact,
                operator=condition.operator,
                expected=condition.expected,
                actual=condition.actual,
                origin=(
                    RuleFactOrigin.INFERRED if producer is not None else RuleFactOrigin.INPUT
                ),
                producer_rule_id=producer[0] if producer is not None else None,
                producer_rule_version=producer[1] if producer is not None else None,
            )
        )

    return RuleDerivationTrace(
        sequence=sequence,
        cycle=cycle,
        rule_id=rule.rule_id,
        version=rule.version,
        priority=rule.priority,
        conditions=condition_evidence,
        normative_refs=list(conclusion.normative_refs),
        source_refs=list(conclusion.source_refs),
        conclusion_code=conclusion.conclusion_code,
        conclusion=conclusion.conclusion,
        requires_human_review=conclusion.requires_human_review,
    )


def evaluate_rules(
    rule_set: RuleSet,
    facts: Mapping[str, Any],
    applicable_normative_refs: set[str] | None = None,
    *,
    max_cycles: int = 20,
) -> RuleEvaluationResult:
    """Evalúa reglas RBR con encadenamiento hacia adelante hasta punto fijo."""
    if len(facts) > 500:
        raise RuleEvaluationError("Máximo 500 hechos por evaluación.")
    if max_cycles < 1:
        raise RuleEvaluationError("max_cycles debe ser mayor o igual a 1.")

    working_facts = dict(facts)
    producers: dict[str, tuple[str, str] | None] = {name: None for name in facts}
    ordered = _ordered_rules(rule_set)
    fired: set[tuple[str, str]] = set()
    conclusions: list[RuleConclusion] = []
    traces: list[RuleTrace] = []
    derivations: list[RuleDerivationTrace] = []
    requires_human_review = False

    for cycle in range(1, max_cycles + 1):
        new_inference = False
        cycle_traces: list[RuleTrace] = []

        for rule in ordered:
            key = (rule.rule_id, rule.version)
            if key in fired:
                continue

            trace, conclusion = evaluate_rule(
                rule,
                working_facts,
                applicable_normative_refs,
            )
            cycle_traces.append(trace)
            if conclusion is None:
                continue

            derivations.append(
                _build_derivation(
                    sequence=len(derivations) + 1,
                    cycle=cycle,
                    rule=rule,
                    trace=trace,
                    conclusion=conclusion,
                    producers=producers,
                )
            )
            fired.add(key)
            conclusions.append(conclusion)
            working_facts[conclusion.conclusion_code] = True
            producers[conclusion.conclusion_code] = (rule.rule_id, rule.version)
            requires_human_review = (
                requires_human_review or conclusion.requires_human_review
            )
            new_inference = True

        traces.extend(cycle_traces)
        if not new_inference:
            return RuleEvaluationResult(
                matched_rules=conclusions,
                traces=traces,
                derivations=derivations,
                requires_human_review=requires_human_review,
            )

    raise RuleEvaluationError(
        "El encadenamiento RBR excedió el máximo de ciclos permitido."
    )
