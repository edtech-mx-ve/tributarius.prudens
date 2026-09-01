from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.domain.isr import ISRPeriod
from app.domain.rules import RuleEvaluationResult
from app.services.rbr_isr_bridge import (
    RBRISRBridgeError,
    build_isr_input_from_rbr,
    calculate_isr_from_rbr,
)
from app.services.rule_engine import evaluate_rules
from calculators.isr_tariff_registry import load_isr_tariff

CONTROLLED_TARIFF = Path(
    "calculators/tariffs/isr_annual_lisr_article_152_2024.json"
)


def _professional_rule_result() -> RuleEvaluationResult:
    import json

    from app.domain.rules import RuleSet

    payload = json.loads(
        Path("rules/production/mvp_isr_professional.json").read_text(encoding="utf-8")
    )
    rule_set = RuleSet.model_validate(payload)
    return evaluate_rules(
        rule_set,
        {
            "taxpayer_type": "individual",
            "income_type": "independent_professional_service",
        },
        {"lisr:articulo_100"},
    )


def _calculation_facts() -> dict[str, object]:
    return {
        "fiscal_year": 2024,
        "isr_period": "annual",
        "gross_income": "100000.00",
        "exempt_income": "0.00",
        "authorized_deductions": "0.00",
        "credits": "0.00",
    }


def test_rbr_payment_obligation_builds_deterministic_isr_input() -> None:
    tariff = load_isr_tariff(CONTROLLED_TARIFF)
    rule_result = _professional_rule_result()

    calculation_input = build_isr_input_from_rbr(
        rule_result,
        _calculation_facts(),
        tariff,
    )

    assert calculation_input is not None
    assert calculation_input.fiscal_year == 2024
    assert calculation_input.period == ISRPeriod.ANNUAL
    assert calculation_input.gross_income == Decimal("100000.00")
    assert calculation_input.normative_ref == "lisr:articulo_152"


def test_rbr_without_payment_obligation_does_not_calculate() -> None:
    tariff = load_isr_tariff(CONTROLLED_TARIFF)
    empty_result = RuleEvaluationResult(
        matched_rules=[],
        traces=[],
        derivations=[],
        requires_human_review=False,
    )

    assert build_isr_input_from_rbr(empty_result, _calculation_facts(), tariff) is None
    assert calculate_isr_from_rbr(empty_result, _calculation_facts(), tariff) is None


def test_rbr_trigger_fails_closed_when_required_amount_is_missing() -> None:
    tariff = load_isr_tariff(CONTROLLED_TARIFF)
    facts = _calculation_facts()
    facts.pop("gross_income")

    with pytest.raises(RBRISRBridgeError, match="gross_income"):
        build_isr_input_from_rbr(_professional_rule_result(), facts, tariff)


def test_rbr_trigger_fails_closed_when_period_is_missing() -> None:
    tariff = load_isr_tariff(CONTROLLED_TARIFF)
    facts = _calculation_facts()
    facts.pop("isr_period")

    with pytest.raises(RBRISRBridgeError, match="isr_period"):
        build_isr_input_from_rbr(_professional_rule_result(), facts, tariff)


def test_rbr_trigger_rejects_unsupported_period() -> None:
    tariff = load_isr_tariff(CONTROLLED_TARIFF)
    facts = _calculation_facts()
    facts["isr_period"] = "weekly"

    with pytest.raises(RBRISRBridgeError, match="periodicidad ISR soportada"):
        build_isr_input_from_rbr(_professional_rule_result(), facts, tariff)


def test_rbr_drives_reproducible_deterministic_isr_calculation() -> None:
    tariff = load_isr_tariff(CONTROLLED_TARIFF)
    rule_result = _professional_rule_result()
    facts = _calculation_facts()

    first = calculate_isr_from_rbr(rule_result, facts, tariff)
    second = calculate_isr_from_rbr(rule_result, facts, tariff)

    assert first is not None
    assert second is not None
    assert first == second
    assert first.taxable_base == Decimal("100000.00")
    assert first.final_tax == Decimal("8923.59")
    assert first.tariff_version == "LISR-ART152-CORPUS-2024"
