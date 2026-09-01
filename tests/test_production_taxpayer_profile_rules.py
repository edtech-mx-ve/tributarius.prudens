import json
from pathlib import Path

from app.domain.rules import RuleSet
from app.services.rule_engine import evaluate_rules

RULES_PATH = Path("rules/production/mvp_taxpayer_profile.json")
CFF_ART_1 = "cff:articulo_1"
CFF_ART_2 = "cff:articulo_2"


def _rule_set() -> RuleSet:
    return RuleSet.model_validate(
        json.loads(RULES_PATH.read_text(encoding="utf-8"))
    )


def test_profile_rules_use_real_cff_references() -> None:
    rule_set = _rule_set()

    assert len(rule_set.rules) == 3
    refs = {ref for rule in rule_set.rules for ref in rule.normative_refs}
    assert refs == {CFF_ART_1, CFF_ART_2}
    assert all(rule.source_refs for rule in rule_set.rules)
    assert all("TEST" not in ref.upper() for ref in refs)


def test_individual_profile_is_derived_from_explicit_subject_fact() -> None:
    result = evaluate_rules(
        _rule_set(),
        {"taxpayer_type": "individual"},
        {CFF_ART_1, CFF_ART_2},
    )

    assert [item.conclusion_code for item in result.matched_rules] == [
        "individual_taxpayer_profile"
    ]


def test_legal_entity_profile_is_kept_distinct() -> None:
    result = evaluate_rules(
        _rule_set(),
        {"taxpayer_type": "legal_entity"},
        {CFF_ART_1, CFF_ART_2},
    )

    assert [item.conclusion_code for item in result.matched_rules] == [
        "legal_entity_taxpayer_profile"
    ]


def test_profile_chain_requires_explicit_taxable_situation() -> None:
    result = evaluate_rules(
        _rule_set(),
        {
            "taxpayer_type": "individual",
            "taxable_legal_or_factual_situation": True,
        },
        {CFF_ART_1, CFF_ART_2},
    )

    assert [item.conclusion_code for item in result.matched_rules] == [
        "individual_taxpayer_profile",
        "specific_tax_law_required",
    ]


def test_profile_rules_do_not_invent_missing_subject() -> None:
    result = evaluate_rules(
        _rule_set(),
        {"taxable_legal_or_factual_situation": True},
        {CFF_ART_1, CFF_ART_2},
    )

    assert result.matched_rules == []


def test_profile_rules_are_blocked_without_normative_support() -> None:
    result = evaluate_rules(
        _rule_set(),
        {"taxpayer_type": "individual"},
        set(),
    )

    assert result.matched_rules == []
