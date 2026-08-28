import pytest
from pydantic import ValidationError

from app.domain.rules import RuleCondition, RuleDefinition, RuleOperator, RuleSet


def test_in_requires_list() -> None:
    with pytest.raises(ValidationError):
        RuleCondition(fact="regime", operator=RuleOperator.IN, value="x")


def test_duplicate_rule_version_rejected() -> None:
    rule = RuleDefinition(
        rule_id="RULE_DUP_001",
        version="1.0",
        description="Prueba.",
        conditions=[RuleCondition(fact="active", operator=RuleOperator.EQ, value=True)],
        conclusion_code="duplicate",
        conclusion="Duplicada.",
    )
    with pytest.raises(ValidationError):
        RuleSet(schema_version="1.0", rules=[rule, rule])
