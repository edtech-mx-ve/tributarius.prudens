from __future__ import annotations

import json
from pathlib import Path

from app.domain.rules import RuleEvaluationResult, RuleFactOrigin, RuleSet
from app.services.rule_engine import evaluate_rules

PRODUCTION_RULE_FILES = (
    Path("rules/production/mvp_taxpayer_profile.json"),
    Path("rules/production/mvp_income_classification.json"),
    Path("rules/production/mvp_isr_professional.json"),
    Path("rules/production/mvp_obligations_rights.json"),
)

CFF_1 = "cff:articulo_1"
LISR_100 = "lisr:articulo_100"
LISR_110 = "lisr:articulo_110"
LFDC_2 = "lfdc:articulo_2"

PROFESSIONAL_REFS = {CFF_1, LISR_100, LISR_110, LFDC_2}


def _production_rule_set() -> RuleSet:
    rules = []
    for path in PRODUCTION_RULE_FILES:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rules.extend(RuleSet.model_validate(payload).rules)
    return RuleSet(schema_version="1.0", rules=rules)


def _codes(result: RuleEvaluationResult) -> list[str]:
    return [item.conclusion_code for item in result.matched_rules]


def test_professional_case_runs_end_to_end_through_production_rbr() -> None:
    result = evaluate_rules(
        _production_rule_set(),
        {
            "taxpayer_type": "individual",
            "income_type": "independent_professional_service",
        },
        PROFESSIONAL_REFS,
    )

    codes = _codes(result)

    assert "individual_taxpayer_profile" in codes
    assert "professional_service_income" in codes
    assert "isr_professional_payment_obligation" in codes
    assert "rfc_registration_obligation" in codes
    assert "accounting_obligation" in codes
    assert "income_cfdi_obligation" in codes
    assert "right_information_and_assistance" in codes
    assert "right_tax_data_confidentiality" in codes
    assert "right_respectful_treatment" in codes


def test_professional_case_reconstructs_derived_fact_dependencies() -> None:
    result = evaluate_rules(
        _production_rule_set(),
        {
            "taxpayer_type": "individual",
            "income_type": "independent_professional_service",
        },
        PROFESSIONAL_REFS,
    )

    derivations = {item.rule_id: item for item in result.derivations}

    payment = derivations["ISR_PROFESSIONAL_PAYMENT_002"]
    payment_condition = next(
        item for item in payment.conditions if item.fact == "professional_service_income"
    )
    assert payment_condition.origin == RuleFactOrigin.INFERRED
    assert payment_condition.producer_rule_id == "ISR_PROFESSIONAL_CLASSIFY_001"
    assert payment_condition.producer_rule_version == "1.0.0"

    rfc = derivations["OBL_PROFESSIONAL_RFC_001"]
    rfc_condition = next(
        item for item in rfc.conditions if item.fact == "professional_service_income"
    )
    assert rfc_condition.origin == RuleFactOrigin.INFERRED
    assert rfc_condition.producer_rule_id == "ISR_PROFESSIONAL_CLASSIFY_001"

    right = derivations["RIGHT_INFORMATION_ASSISTANCE_004"]
    right_condition = next(
        item for item in right.conditions if item.fact == "individual_taxpayer_profile"
    )
    assert right_condition.origin == RuleFactOrigin.INFERRED
    assert right_condition.producer_rule_id == "PROFILE_INDIVIDUAL_001"


def test_each_production_derivation_preserves_legal_support() -> None:
    result = evaluate_rules(
        _production_rule_set(),
        {
            "taxpayer_type": "individual",
            "income_type": "independent_professional_service",
        },
        PROFESSIONAL_REFS,
    )

    assert result.derivations
    assert all(item.normative_refs for item in result.derivations)
    assert all(item.source_refs for item in result.derivations)
    assert all(item.sequence == index for index, item in enumerate(result.derivations, 1))


def test_missing_lisr_110_blocks_only_formal_professional_obligations() -> None:
    result = evaluate_rules(
        _production_rule_set(),
        {
            "taxpayer_type": "individual",
            "income_type": "independent_professional_service",
        },
        {CFF_1, LISR_100, LFDC_2},
    )

    codes = _codes(result)

    assert "individual_taxpayer_profile" in codes
    assert "professional_service_income" in codes
    assert "isr_professional_payment_obligation" in codes
    assert "right_information_and_assistance" in codes
    assert "rfc_registration_obligation" not in codes
    assert "accounting_obligation" not in codes
    assert "income_cfdi_obligation" not in codes


def test_missing_lfdc_2_blocks_rights_without_erasing_isr_reasoning() -> None:
    result = evaluate_rules(
        _production_rule_set(),
        {
            "taxpayer_type": "individual",
            "income_type": "independent_professional_service",
        },
        {CFF_1, LISR_100, LISR_110},
    )

    codes = _codes(result)

    assert "professional_service_income" in codes
    assert "isr_professional_payment_obligation" in codes
    assert "rfc_registration_obligation" in codes
    assert "right_information_and_assistance" not in codes
    assert "right_tax_data_confidentiality" not in codes
    assert "right_respectful_treatment" not in codes


def test_no_normative_support_produces_no_legal_derivation() -> None:
    result = evaluate_rules(
        _production_rule_set(),
        {
            "taxpayer_type": "individual",
            "income_type": "independent_professional_service",
        },
        set(),
    )

    assert result.matched_rules == []
    assert result.derivations == []
    assert result.requires_human_review is False
