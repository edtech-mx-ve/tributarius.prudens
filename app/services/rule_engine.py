from __future__ import annotations

from collections.abc import Mapping
from numbers import Real
from typing import Any

from app.domain.rules import (
    ConditionTrace,
    RuleConclusion,
    RuleCondition,
    RuleDefinition,
    RuleEvaluationResult,
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


def evaluate_rules(
    rule_set: RuleSet,
    facts: Mapping[str, Any],
    applicable_normative_refs: set[str] | None = None,
) -> RuleEvaluationResult:
    if len(facts) > 500:
        raise RuleEvaluationError("Máximo 500 hechos por evaluación.")

    ordered = sorted(
        rule_set.rules,
        key=lambda rule: (-rule.priority, rule.rule_id, rule.version),
    )
    traces: list[RuleTrace] = []
    conclusions: list[RuleConclusion] = []
    for rule in ordered:
        trace, conclusion = evaluate_rule(rule, facts, applicable_normative_refs)
        traces.append(trace)
        if conclusion is not None:
            conclusions.append(conclusion)

    return RuleEvaluationResult(
        matched_rules=conclusions,
        traces=traces,
        requires_human_review=any(item.requires_human_review for item in conclusions),
    )
