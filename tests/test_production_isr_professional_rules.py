import json
from pathlib import Path

from app.domain.rules import RuleSet
from app.services.rule_engine import evaluate_rules

RULES_PATH = Path("rules/production/mvp_isr_professional.json")
LEGAL_REF = "lisr:articulo_100"


def _rule_set() -> RuleSet:
    payload = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    return RuleSet.model_validate(payload)


def test_production_rules_are_grounded_in_lisr_article_100() -> None:
    rule_set = _rule_set()

    assert len(rule_set.rules) == 2
    assert all(rule.normative_refs == [LEGAL_REF] for rule in rule_set.rules)
    assert all(rule.source_refs for rule in rule_set.rules)
    assert all("TEST" not in ref.upper() for rule in rule_set.rules for ref in rule.normative_refs)


def test_professional_income_rules_chain_with_normative_support() -> None:
    result = evaluate_rules(
        _rule_set(),
        {
            "taxpayer_type": "individual",
            "income_type": "independent_professional_service",
        },
        {LEGAL_REF},
    )

    assert [item.rule_id for item in result.matched_rules] == [
        "ISR_PROFESSIONAL_CLASSIFY_001",
        "ISR_PROFESSIONAL_PAYMENT_002",
    ]
    assert [item.conclusion_code for item in result.matched_rules] == [
        "professional_service_income",
        "isr_professional_payment_obligation",
    ]


def test_professional_income_rules_do_not_fire_without_normative_support() -> None:
    result = evaluate_rules(
        _rule_set(),
        {
            "taxpayer_type": "individual",
            "income_type": "independent_professional_service",
        },
        set(),
    )

    assert result.matched_rules == []
    assert result.traces
    assert all(
        trace.skipped_reason == "Faltan referencias normativas aplicables."
        for trace in result.traces
    )
