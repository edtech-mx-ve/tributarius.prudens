import pytest

from app.domain.rules import RuleCondition, RuleDefinition, RuleOperator, RuleSet
from app.services.rule_engine import RuleEvaluationError, evaluate_condition, evaluate_rules


def make_rules() -> RuleSet:
    return RuleSet(
        schema_version="1.0",
        rules=[
            RuleDefinition(
                rule_id="RULE_HIGH_001",
                version="1.0",
                description="Regla prioritaria.",
                priority=200,
                conditions=[
                    RuleCondition(
                        fact="taxpayer_type",
                        operator=RuleOperator.EQ,
                        value="individual",
                    )
                ],
                conclusion_code="high_match",
                conclusion="Coincidencia prioritaria.",
                normative_refs=["NORM_2026"],
            ),
            RuleDefinition(
                rule_id="RULE_LOW_001",
                version="1.0",
                description="Regla secundaria.",
                priority=100,
                conditions=[
                    RuleCondition(fact="income", operator=RuleOperator.GTE, value=1000)
                ],
                conclusion_code="low_match",
                conclusion="Coincidencia secundaria.",
            ),
        ],
    )


def test_numeric_condition() -> None:
    condition = RuleCondition(fact="income", operator=RuleOperator.GT, value=100)
    assert evaluate_condition(condition, {"income": 150}).matched is True


def test_missing_fact_does_not_match() -> None:
    condition = RuleCondition(fact="income", operator=RuleOperator.GT, value=100)
    assert evaluate_condition(condition, {}).matched is False


def test_deterministic_priority_order() -> None:
    result = evaluate_rules(
        make_rules(),
        {"taxpayer_type": "individual", "income": 2000},
        {"NORM_2026"},
    )
    assert [item.rule_id for item in result.matched_rules] == [
        "RULE_HIGH_001",
        "RULE_LOW_001",
    ]


def test_normative_dependency_blocks_rule() -> None:
    result = evaluate_rules(
        make_rules(),
        {"taxpayer_type": "individual"},
        set(),
    )
    assert result.matched_rules == []
    assert result.traces[0].skipped_reason == "Faltan referencias normativas aplicables."


def test_disabled_rule_is_traced() -> None:
    rules = make_rules()
    rules.rules[0].enabled = False
    result = evaluate_rules(rules, {"taxpayer_type": "individual"}, {"NORM_2026"})
    assert result.traces[0].skipped_reason == "Regla deshabilitada."


def test_human_review_propagates() -> None:
    rules = make_rules()
    rules.rules[1].requires_human_review = True
    result = evaluate_rules(rules, {"income": 2000}, set())
    assert result.requires_human_review is True


def test_fact_limit() -> None:
    with pytest.raises(RuleEvaluationError):
        evaluate_rules(make_rules(), {f"fact_{i}": i for i in range(501)}, set())
