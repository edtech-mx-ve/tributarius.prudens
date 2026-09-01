from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain.isr import (
    ISRBracket,
    ISRCalculationInput,
    ISRPeriod,
    ISRTariff,
)
from calculators.isr import (
    ISRCalculationError,
    calculate_isr,
    money,
    select_bracket,
    validate_tariff,
)

NORMATIVE_REF = "lisr:articulo_106"


def _tariff(
    *,
    fiscal_year: int = 2026,
    period: ISRPeriod = ISRPeriod.MONTHLY,
    normative_ref: str = NORMATIVE_REF,
) -> ISRTariff:
    return ISRTariff(
        schema_version="1.0",
        version="audit-6.1",
        fiscal_year=fiscal_year,
        period=period,
        normative_ref=normative_ref,
        source_reference="Fuente controlada de prueba para auditoría determinística.",
        verified=True,
        brackets=[
            ISRBracket(
                lower_limit=Decimal("0.00"),
                upper_limit=Decimal("1000.00"),
                fixed_fee=Decimal("0.00"),
                rate_percent=Decimal("10.00"),
            ),
            ISRBracket(
                lower_limit=Decimal("1000.01"),
                upper_limit=Decimal("5000.00"),
                fixed_fee=Decimal("100.00"),
                rate_percent=Decimal("20.00"),
            ),
            ISRBracket(
                lower_limit=Decimal("5000.01"),
                upper_limit=None,
                fixed_fee=Decimal("900.00"),
                rate_percent=Decimal("30.00"),
            ),
        ],
    )


def _input(
    *,
    fiscal_year: int = 2026,
    period: ISRPeriod = ISRPeriod.MONTHLY,
    gross_income: str = "4000.00",
    exempt_income: str = "500.00",
    authorized_deductions: str = "500.00",
    credits: str = "50.00",
    normative_ref: str = NORMATIVE_REF,
) -> ISRCalculationInput:
    return ISRCalculationInput(
        fiscal_year=fiscal_year,
        period=period,
        gross_income=Decimal(gross_income),
        exempt_income=Decimal(exempt_income),
        authorized_deductions=Decimal(authorized_deductions),
        credits=Decimal(credits),
        normative_ref=normative_ref,
    )


def test_money_rounds_half_up_to_cents() -> None:
    assert money(Decimal("10.005")) == Decimal("10.01")
    assert money(Decimal("10.004")) == Decimal("10.00")


@pytest.mark.parametrize(
    ("base", "expected_lower"),
    [
        ("0.00", "0.00"),
        ("1000.00", "0.00"),
        ("1000.01", "1000.01"),
        ("5000.00", "1000.01"),
        ("5000.01", "5000.01"),
        ("999999.99", "5000.01"),
    ],
)
def test_select_bracket_respects_exact_boundaries(
    base: str,
    expected_lower: str,
) -> None:
    bracket = select_bracket(Decimal(base), _tariff())
    assert bracket.lower_limit == Decimal(expected_lower)


def test_calculation_is_reproducible_and_reconstructable() -> None:
    result = calculate_isr(_input(), _tariff())

    assert result.taxable_base == Decimal("3000.00")
    assert result.selected_lower_limit == Decimal("1000.01")
    assert result.selected_upper_limit == Decimal("5000.00")
    assert result.fixed_fee == Decimal("100.00")
    assert result.rate_percent == Decimal("20.00")
    assert result.tax_before_credits == Decimal("500.00")
    assert result.credits == Decimal("50.00")
    assert result.final_tax == Decimal("450.00")
    assert result.normative_ref == NORMATIVE_REF
    assert result.tariff_version == "audit-6.1"
    assert [step.code for step in result.steps] == [
        "taxable_base",
        "excess_over_lower_limit",
        "marginal_tax",
        "tax_before_credits",
        "final_tax",
    ]
    assert [step.result for step in result.steps] == [
        Decimal("3000.00"),
        Decimal("1999.99"),
        Decimal("400.00"),
        Decimal("500.00"),
        Decimal("450.00"),
    ]


def test_credits_never_make_final_tax_negative() -> None:
    result = calculate_isr(
        _input(
            gross_income="500.00",
            exempt_income="0",
            authorized_deductions="0",
            credits="999.00",
        ),
        _tariff(),
    )
    assert result.tax_before_credits == Decimal("50.00")
    assert result.final_tax == Decimal("0.00")


def test_negative_computed_taxable_base_is_rejected() -> None:
    with pytest.raises(
        ISRCalculationError,
        match="La base gravable calculada no puede ser negativa",
    ):
        calculate_isr(
            _input(
                gross_income="1000.00",
                exempt_income="0",
                authorized_deductions="1500.00",
            ),
            _tariff(),
        )


def test_input_rejects_exempt_income_above_gross_income() -> None:
    with pytest.raises(ValidationError):
        _input(gross_income="1000.00", exempt_income="1000.01")


def test_unverified_tariff_is_rejected_by_domain_contract() -> None:
    with pytest.raises(ValidationError):
        ISRTariff(
            schema_version="1.0",
            version="unverified",
            fiscal_year=2026,
            period=ISRPeriod.MONTHLY,
            normative_ref=NORMATIVE_REF,
            source_reference="Fuente no verificada.",
            verified=False,
            brackets=[
                ISRBracket(
                    lower_limit=Decimal("0.00"),
                    upper_limit=None,
                    fixed_fee=Decimal("0.00"),
                    rate_percent=Decimal("10.00"),
                )
            ],
        )


def test_calculation_rejects_fiscal_year_mismatch() -> None:
    with pytest.raises(
        ISRCalculationError,
        match="El ejercicio fiscal de la entrada no coincide",
    ):
        calculate_isr(_input(fiscal_year=2025), _tariff(fiscal_year=2026))


def test_calculation_rejects_period_mismatch() -> None:
    with pytest.raises(
        ISRCalculationError,
        match="La periodicidad de la entrada no coincide",
    ):
        calculate_isr(
            _input(period=ISRPeriod.ANNUAL),
            _tariff(period=ISRPeriod.MONTHLY),
        )


def test_calculation_rejects_normative_reference_mismatch() -> None:
    with pytest.raises(
        ISRCalculationError,
        match="La referencia normativa validada no coincide",
    ):
        calculate_isr(
            _input(normative_ref="lisr:articulo_999"),
            _tariff(normative_ref=NORMATIVE_REF),
        )


def test_tariff_rejects_overlapping_brackets() -> None:
    tariff = ISRTariff(
        schema_version="1.0",
        version="overlap",
        fiscal_year=2026,
        period=ISRPeriod.MONTHLY,
        normative_ref=NORMATIVE_REF,
        source_reference="Fuente controlada de prueba.",
        verified=True,
        brackets=[
            ISRBracket(
                lower_limit=Decimal("0.00"),
                upper_limit=Decimal("1000.00"),
                fixed_fee=Decimal("0.00"),
                rate_percent=Decimal("10.00"),
            ),
            ISRBracket(
                lower_limit=Decimal("999.99"),
                upper_limit=None,
                fixed_fee=Decimal("100.00"),
                rate_percent=Decimal("20.00"),
            ),
        ],
    )

    with pytest.raises(ISRCalculationError, match="se traslapan"):
        validate_tariff(tariff)


def test_tariff_rejects_open_range_before_last_bracket() -> None:
    tariff = ISRTariff(
        schema_version="1.0",
        version="open-before-last",
        fiscal_year=2026,
        period=ISRPeriod.MONTHLY,
        normative_ref=NORMATIVE_REF,
        source_reference="Fuente controlada de prueba.",
        verified=True,
        brackets=[
            ISRBracket(
                lower_limit=Decimal("0.00"),
                upper_limit=None,
                fixed_fee=Decimal("0.00"),
                rate_percent=Decimal("10.00"),
            ),
            ISRBracket(
                lower_limit=Decimal("1000.01"),
                upper_limit=None,
                fixed_fee=Decimal("100.00"),
                rate_percent=Decimal("20.00"),
            ),
        ],
    )

    with pytest.raises(
        ISRCalculationError,
        match="Solo el último rango puede carecer de límite superior",
    ):
        validate_tariff(tariff)


def test_gap_between_brackets_fails_closed_when_base_has_no_range() -> None:
    tariff = ISRTariff(
        schema_version="1.0",
        version="gap",
        fiscal_year=2026,
        period=ISRPeriod.MONTHLY,
        normative_ref=NORMATIVE_REF,
        source_reference="Fuente controlada de prueba.",
        verified=True,
        brackets=[
            ISRBracket(
                lower_limit=Decimal("0.00"),
                upper_limit=Decimal("1000.00"),
                fixed_fee=Decimal("0.00"),
                rate_percent=Decimal("10.00"),
            ),
            ISRBracket(
                lower_limit=Decimal("2000.00"),
                upper_limit=None,
                fixed_fee=Decimal("100.00"),
                rate_percent=Decimal("20.00"),
            ),
        ],
    )

    validate_tariff(tariff)
    with pytest.raises(
        ISRCalculationError,
        match="La base gravable no pertenece a ningún rango",
    ):
        select_bracket(Decimal("1500.00"), tariff)
