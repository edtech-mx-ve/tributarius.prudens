import json
from pathlib import Path

from app.domain.rules import RuleSet
from app.services.rule_engine import evaluate_rules

RULES_PATH = Path("rules/production/mvp_obligations_rights.json")
LISR_110 = "lisr:articulo_110"
LFDC_2 = "lfdc:articulo_2"
ALL_REFS = {LISR_110, LFDC_2}


def _rule_set() -> RuleSet:
    return RuleSet.model_validate(json.loads(RULES_PATH.read_text(encoding="utf-8")))


def test_obligation_and_right_rules_use_controlled_legal_refs() -> None:
    rule_set = _rule_set()

    assert len(rule_set.rules) == 6
    refs = {ref for rule in rule_set.rules for ref in rule.normative_refs}
    assert refs == ALL_REFS
    assert all(rule.source_refs for rule in rule_set.rules)
    assert all("TEST" not in ref.upper() for ref in refs)


def test_professional_income_derives_core_formal_obligations() -> None:
    result = evaluate_rules(
        _rule_set(),
        {"professional_service_income": True},
        {LISR_110},
    )

    assert [item.conclusion_code for item in result.matched_rules] == [
        "rfc_registration_obligation",
        "accounting_obligation",
        "income_cfdi_obligation",
    ]


def test_individual_profile_derives_general_taxpayer_rights() -> None:
    result = evaluate_rules(
        _rule_set(),
        {"individual_taxpayer_profile": True},
        {LFDC_2},
    )

    assert [item.conclusion_code for item in result.matched_rules] == [
        "right_information_and_assistance",
        "right_tax_data_confidentiality",
        "right_respectful_treatment",
    ]


def test_obligations_do_not_fire_from_profile_alone() -> None:
    result = evaluate_rules(
        _rule_set(),
        {"individual_taxpayer_profile": True},
        ALL_REFS,
    )

    codes = [item.conclusion_code for item in result.matched_rules]
    assert "rfc_registration_obligation" not in codes
    assert "accounting_obligation" not in codes
    assert "income_cfdi_obligation" not in codes


def test_rights_do_not_require_professional_income() -> None:
    result = evaluate_rules(
        _rule_set(),
        {"professional_service_income": True},
        ALL_REFS,
    )

    codes = [item.conclusion_code for item in result.matched_rules]
    assert "right_information_and_assistance" not in codes
    assert "right_tax_data_confidentiality" not in codes
    assert "right_respectful_treatment" not in codes


def test_missing_normative_support_blocks_obligations_and_rights() -> None:
    result = evaluate_rules(
        _rule_set(),
        {
            "professional_service_income": True,
            "individual_taxpayer_profile": True,
        },
        set(),
    )

    assert result.matched_rules == []
