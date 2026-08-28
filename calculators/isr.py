from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.domain.isr import (
    ISRBracket,
    ISRCalculationInput,
    ISRCalculationResult,
    ISRCalculationStep,
    ISRTariff,
)


class ISRCalculationError(ValueError):
    """Error controlado del cálculo determinista de ISR."""


CENT = Decimal("0.01")
HUNDRED = Decimal("100")


def money(value: Decimal) -> Decimal:
    """Redondea importes monetarios a centavos con ROUND_HALF_UP."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def validate_tariff(tariff: ISRTariff) -> None:
    """Valida continuidad lógica y ausencia de traslapes en la tarifa."""
    previous_upper: Decimal | None = None
    for index, bracket in enumerate(tariff.brackets):
        if bracket.upper_limit is not None and bracket.upper_limit < bracket.lower_limit:
            raise ISRCalculationError("Un límite superior es menor al límite inferior.")
        if index > 0 and previous_upper is None:
            raise ISRCalculationError("Solo el último rango puede carecer de límite superior.")
        if previous_upper is not None and bracket.lower_limit <= previous_upper:
            raise ISRCalculationError("Los rangos de la tarifa se traslapan.")
        previous_upper = bracket.upper_limit


def select_bracket(taxable_base: Decimal, tariff: ISRTariff) -> ISRBracket:
    """Selecciona el rango aplicable sin inferencia generativa."""
    for bracket in tariff.brackets:
        upper_ok = bracket.upper_limit is None or taxable_base <= bracket.upper_limit
        if taxable_base >= bracket.lower_limit and upper_ok:
            return bracket
    raise ISRCalculationError("La base gravable no pertenece a ningún rango de la tarifa.")


def calculate_isr(
    calculation_input: ISRCalculationInput,
    tariff: ISRTariff,
) -> ISRCalculationResult:
    """Calcula ISR con una tarifa previamente validada y trazable."""
    validate_tariff(tariff)

    if calculation_input.fiscal_year != tariff.fiscal_year:
        raise ISRCalculationError(
            "El ejercicio fiscal de la entrada no coincide con el de la tarifa."
        )
    if calculation_input.period != tariff.period:
        raise ISRCalculationError(
            "La periodicidad de la entrada no coincide con la de la tarifa."
        )
    if calculation_input.normative_ref != tariff.normative_ref:
        raise ISRCalculationError(
            "La referencia normativa validada no coincide con la tarifa."
        )

    taxable_base = money(
        calculation_input.gross_income
        - calculation_input.exempt_income
        - calculation_input.authorized_deductions
    )
    if taxable_base < 0:
        raise ISRCalculationError("La base gravable calculada no puede ser negativa.")

    bracket = select_bracket(taxable_base, tariff)
    excess = money(taxable_base - bracket.lower_limit)
    marginal_tax = money(excess * bracket.rate_percent / HUNDRED)
    tax_before_credits = money(bracket.fixed_fee + marginal_tax)
    final_tax = money(max(Decimal("0"), tax_before_credits - calculation_input.credits))

    steps = [
        ISRCalculationStep(
            code="taxable_base",
            formula="gross_income - exempt_income - authorized_deductions",
            result=taxable_base,
        ),
        ISRCalculationStep(
            code="excess_over_lower_limit",
            formula="taxable_base - lower_limit",
            result=excess,
        ),
        ISRCalculationStep(
            code="marginal_tax",
            formula="excess_over_lower_limit * rate_percent / 100",
            result=marginal_tax,
        ),
        ISRCalculationStep(
            code="tax_before_credits",
            formula="fixed_fee + marginal_tax",
            result=tax_before_credits,
        ),
        ISRCalculationStep(
            code="final_tax",
            formula="max(0, tax_before_credits - credits)",
            result=final_tax,
        ),
    ]

    return ISRCalculationResult(
        fiscal_year=calculation_input.fiscal_year,
        period=calculation_input.period,
        taxable_base=taxable_base,
        selected_lower_limit=bracket.lower_limit,
        selected_upper_limit=bracket.upper_limit,
        fixed_fee=bracket.fixed_fee,
        rate_percent=bracket.rate_percent,
        tax_before_credits=tax_before_credits,
        credits=calculation_input.credits,
        final_tax=final_tax,
        normative_ref=tariff.normative_ref,
        tariff_version=tariff.version,
        source_reference=tariff.source_reference,
        steps=steps,
    )
