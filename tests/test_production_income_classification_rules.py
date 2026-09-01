import json
from pathlib import Path

import pytest

from app.domain.rules import RuleSet
from app.services.rule_engine import evaluate_rules

RULES_PATH = Path("rules/production/mvp_income_classification.json")
LISR_94 = "lisr:articulo_94"
LISR_100 = "lisr:articulo_100"
LISR_114 = "lisr:articulo_114"
ALL_REFS = {LISR_94, LISR_100, LISR_114}


def _rule_set() -> RuleSet:
    return RuleSet.model_validate(json.loads(RULES_PATH.read_text(encoding="utf-8")))


def test_income_rules_are_grounded_in_real_lisr_articles() -> None:
    rule_set = _rule_set()

    assert len(rule_set.rules) == 3
    refs = {ref for rule in rule_set.rules for ref in rule.normative_refs}
    assert refs == ALL_REFS
    assert all(rule.source_refs for rule in rule_set.rules)
    assert all("TEST" not in ref.upper() for ref in refs)


@pytest.mark.parametrize(
    ("income_type", "expected"),
    [
        ("subordinate_personal_service", "salary_income"),
        ("business_activity", "business_activity_income"),
        ("real_estate_rental", "real_estate_rental_income"),
    ],
)
def test_explicit_income_type_is_classified(
    income_type: str,
    expected: str,
) -> None:
    result = evaluate_rules(
        _rule_set(),
        {"taxpayer_type": "individual", "income_type": income_type},
        ALL_REFS,
    )

    assert [item.conclusion_code for item in result.matched_rules] == [expected]


def test_professional_income_remains_owned_by_existing_professional_rules() -> None:
    result = evaluate_rules(
        _rule_set(),
        {
            "taxpayer_type": "individual",
            "income_type": "independent_professional_service",
        },
        ALL_REFS,
    )

    assert result.matched_rules == []


def test_income_classification_does_not_invent_missing_income_type() -> None:
    result = evaluate_rules(
        _rule_set(),
        {"taxpayer_type": "individual"},
        ALL_REFS,
    )

    assert result.matched_rules == []


def test_income_classification_requires_individual_profile_fact() -> None:
    result = evaluate_rules(
        _rule_set(),
        {"income_type": "subordinate_personal_service"},
        ALL_REFS,
    )

    assert result.matched_rules == []


def test_each_income_class_is_blocked_without_its_normative_support() -> None:
    result = evaluate_rules(
        _rule_set(),
        {
            "taxpayer_type": "individual",
            "income_type": "real_estate_rental",
        },
        {LISR_94, LISR_100},
    )

    assert result.matched_rules == []
