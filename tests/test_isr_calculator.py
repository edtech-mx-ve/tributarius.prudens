from decimal import Decimal

import pytest

from app.domain.isr import ISRBracket, ISRCalculationInput, ISRPeriod, ISRTariff
from calculators.isr import ISRCalculationError, calculate_isr


def tariff() -> ISRTariff:
    return ISRTariff(
        schema_version="1.0",
        version="TEST",
        fiscal_year=2026,
        period=ISRPeriod.ANNUAL,
        normative_ref="NORM_TEST",
        source_reference="TEST_ONLY",
        verified=True,
        brackets=[
            ISRBracket(
                lower_limit=Decimal("0"),
                upper_limit=Decimal("10000"),
                fixed_fee=Decimal("0"),
                rate_percent=Decimal("10"),
            ),
            ISRBracket(
                lower_limit=Decimal("10000.01"),
                upper_limit=None,
                fixed_fee=Decimal("1000"),
                rate_percent=Decimal("20"),
            ),
        ],
    )


def calculation_input() -> ISRCalculationInput:
    return ISRCalculationInput(
        fiscal_year=2026,
        period=ISRPeriod.ANNUAL,
        gross_income=Decimal("20000"),
        exempt_income=Decimal("1000"),
        authorized_deductions=Decimal("2000"),
        credits=Decimal("100"),
        normative_ref="NORM_TEST",
    )


def test_calculation_is_reproducible() -> None:
    result = calculate_isr(calculation_input(), tariff())
    assert result.taxable_base == Decimal("17000.00")
    assert result.tax_before_credits == Decimal("2400.00")
    assert result.final_tax == Decimal("2300.00")


def test_fiscal_year_must_match() -> None:
    data = calculation_input().model_copy(update={"fiscal_year": 2025})
    with pytest.raises(ISRCalculationError):
        calculate_isr(data, tariff())


def test_normative_reference_must_match() -> None:
    data = calculation_input().model_copy(update={"normative_ref": "OTHER"})
    with pytest.raises(ISRCalculationError):
        calculate_isr(data, tariff())


def test_negative_taxable_base_is_rejected() -> None:
    data = calculation_input().model_copy(
        update={
            "gross_income": Decimal("100"),
            "authorized_deductions": Decimal("200"),
        }
    )
    with pytest.raises(ISRCalculationError):
        calculate_isr(data, tariff())


def test_credit_cannot_make_tax_negative() -> None:
    data = calculation_input().model_copy(update={"credits": Decimal("99999")})
    assert calculate_isr(data, tariff()).final_tax == Decimal("0.00")
