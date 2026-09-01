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
    """API semántica del razonador RBR; delega en el motor integrado."""
    return evaluate_rules(
        rule_set,
        facts,
        applicable_normative_refs,
        max_cycles=max_cycles,
    )
