from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.domain.rules import RuleEvaluationResult, RuleSet
from app.services.rule_engine import evaluate_rules


def infer_rule_facts(
    rule_set: RuleSet,
    facts: Mapping[str, Any],
    applicable_normative_refs: set[str] | None = None,
    *,
    max_cycles: int = 20,
) -> RuleEvaluationResult:
    """Encadena conclusiones RBR como hechos hasta alcanzar un punto fijo."""
    working_facts = dict(facts)
    fired: set[tuple[str, str]] = set()
    matched = []
    traces = []
    requires_human_review = False

    for _ in range(max_cycles):
        result = evaluate_rules(
            rule_set,
            working_facts,
            applicable_normative_refs,
        )
        traces.extend(result.traces)
        requires_human_review = requires_human_review or result.requires_human_review

        new_inference = False
        for conclusion in result.matched_rules:
            key = (conclusion.rule_id, conclusion.version)
            if key in fired:
                continue
            fired.add(key)
            matched.append(conclusion)
            working_facts[conclusion.conclusion_code] = True
            new_inference = True

        if not new_inference:
            return RuleEvaluationResult(
                matched_rules=matched,
                traces=traces,
                requires_human_review=requires_human_review,
            )

    raise RuntimeError("El encadenamiento RBR excedió el máximo de ciclos permitido.")
