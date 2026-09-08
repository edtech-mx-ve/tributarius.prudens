from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.domain.isr import ISRCalculationInput, ISRPeriod
from app.services.hybrid_isr_stage import merge_structured_isr_facts
from app.services.rbr_isr_bridge import (
    RBRISRBridgeError,
    build_isr_input_from_rbr,
    calculate_isr_from_rbr,
)
from app.services.rule_engine import evaluate_rules
from calculators.isr import calculate_isr
from calculators.isr_tariff_registry import load_isr_tariff

CONTROLLED_TARIFF = Path(
    "calculators/tariffs/isr_annual_lisr_article_152_2024.json"
)


def _professional_rule_result():
    import json

    from app.domain.rules import RuleSet

    payload = json.loads(
        Path(
            "rules/production/mvp_isr_professional.json"
        ).read_text(encoding="utf-8")
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


def _declared_base_input() -> ISRCalculationInput:
    return ISRCalculationInput(
        fiscal_year=2024,
        period=ISRPeriod.ANNUAL,
        taxable_base=Decimal("100000.00"),
        credits=Decimal("0"),
        normative_ref="lisr:articulo_152",
    )


def test_calculator_accepts_declared_taxable_base_without_gross_income() -> None:
    tariff = load_isr_tariff(CONTROLLED_TARIFF)

    calculation_input = _declared_base_input()
    result = calculate_isr(
        calculation_input,
        tariff,
    )

    assert calculation_input.gross_income is None
    assert calculation_input.taxable_base == Decimal("100000.00")

    assert result.taxable_base == Decimal("100000.00")
    assert result.final_tax == Decimal("8923.59")

    assert result.steps[0].code == "taxable_base"
    assert result.steps[0].formula == "declared_taxable_base"


def test_rbr_bridge_preserves_declared_taxable_base() -> None:
    tariff = load_isr_tariff(CONTROLLED_TARIFF)

    facts = {
        "fiscal_year": 2024,
        "isr_period": "annual",
        "taxable_base": "100000.00",
        "credits": "0.00",
    }

    calculation_input = build_isr_input_from_rbr(
        _professional_rule_result(),
        facts,
        tariff,
    )

    assert calculation_input is not None
    assert calculation_input.taxable_base == Decimal("100000.00")
    assert calculation_input.gross_income is None

    result = calculate_isr_from_rbr(
        _professional_rule_result(),
        facts,
        tariff,
    )

    assert result is not None
    assert result.taxable_base == Decimal("100000.00")
    assert result.final_tax == Decimal("8923.59")


def test_rbr_bridge_fails_closed_without_any_calculation_base() -> None:
    tariff = load_isr_tariff(CONTROLLED_TARIFF)

    facts = {
        "fiscal_year": 2024,
        "isr_period": "annual",
    }

    with pytest.raises(
        RBRISRBridgeError,
        match="gross_income.*taxable_base",
    ):
        build_isr_input_from_rbr(
            _professional_rule_result(),
            facts,
            tariff,
        )


def test_input_rejects_conflicting_declared_and_derived_base() -> None:
    with pytest.raises(
        ValidationError,
        match="taxable_base contradice",
    ):
        ISRCalculationInput(
            fiscal_year=2024,
            period=ISRPeriod.ANNUAL,
            gross_income=Decimal("100000.00"),
            exempt_income=Decimal("0"),
            authorized_deductions=Decimal("0"),
            taxable_base=Decimal("90000.00"),
            normative_ref="lisr:articulo_152",
        )


def test_input_accepts_consistent_declared_and_derived_base() -> None:
    calculation_input = ISRCalculationInput(
        fiscal_year=2024,
        period=ISRPeriod.ANNUAL,
        gross_income=Decimal("100000.00"),
        exempt_income=Decimal("10000.00"),
        authorized_deductions=Decimal("5000.00"),
        taxable_base=Decimal("85000.00"),
        normative_ref="lisr:articulo_152",
    )

    assert calculation_input.taxable_base == Decimal("85000.00")


def test_declared_base_rejects_income_components_without_gross_income() -> None:
    with pytest.raises(
        ValidationError,
        match="componentes de ingreso",
    ):
        ISRCalculationInput(
            fiscal_year=2024,
            period=ISRPeriod.ANNUAL,
            taxable_base=Decimal("100000.00"),
            authorized_deductions=Decimal("5000.00"),
            normative_ref="lisr:articulo_152",
        )


def test_hybrid_merge_does_not_invent_gross_income() -> None:
    merged = merge_structured_isr_facts(
        {},
        _declared_base_input(),
    )

    assert merged["taxable_base"] == Decimal("100000.00")
    assert "gross_income" not in merged
