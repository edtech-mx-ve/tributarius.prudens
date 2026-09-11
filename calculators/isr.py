from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.domain.isr import (
    ISRBracket,
    ISRCalculationInput,
    ISRCalculationResult,
    ISRCalculationStep,
    ISRPeriod,
    ISRTariff,
    ISRTariffScope,
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

    has_article_106_subtractions = (
        calculation_input.prior_provisional_payments != Decimal("0")
        or calculation_input.isr_withholding != Decimal("0")
    )

    if has_article_106_subtractions and not (
        tariff.period == ISRPeriod.MONTHLY
        and tariff.tariff_scope == ISRTariffScope.YEAR_TO_MONTH
        and tariff.normative_ref == "lisr:articulo_106"
    ):
        raise ISRCalculationError(
            "Los pagos provisionales previos y las retenciones ISR "
            "solo pueden aplicarse al contrato mensual acumulado "
            "controlado del articulo 106."
        )

    if calculation_input.taxable_base is not None:
        if calculation_input.gross_income is None:
            if (
                calculation_input.exempt_income != Decimal("0")
                or calculation_input.authorized_deductions != Decimal("0")
            ):
                raise ISRCalculationError(
                    "No pueden aplicarse componentes de ingreso sin gross_income."
                )

            taxable_base = money(calculation_input.taxable_base)
            taxable_base_formula = "declared_taxable_base"
        else:
            derived_base = money(
                calculation_input.gross_income
                - calculation_input.exempt_income
                - calculation_input.authorized_deductions
            )
            declared_base = money(calculation_input.taxable_base)

            if derived_base != declared_base:
                raise ISRCalculationError(
                    "La base gravable declarada contradice la base derivada."
                )

            taxable_base = declared_base
            taxable_base_formula = (
                "declared_taxable_base == "
                "gross_income - exempt_income - authorized_deductions"
            )
    else:
        if calculation_input.gross_income is None:
            raise ISRCalculationError(
                "No existe una base válida para ejecutar el cálculo ISR."
            )

        taxable_base = money(
            calculation_input.gross_income
            - calculation_input.exempt_income
            - calculation_input.authorized_deductions
        )
        taxable_base_formula = (
            "gross_income - exempt_income - authorized_deductions"
        )

    if taxable_base < 0:
        raise ISRCalculationError(
            "La base gravable calculada no puede ser negativa."
        )

    bracket = select_bracket(taxable_base, tariff)
    excess = money(taxable_base - bracket.lower_limit)
    marginal_tax = money(excess * bracket.rate_percent / HUNDRED)
    tax_before_credits = money(bracket.fixed_fee + marginal_tax)

    prior_provisional_payments = money(
        calculation_input.prior_provisional_payments
    )

    isr_withholding = money(
        calculation_input.isr_withholding
    )

    credits = money(
        calculation_input.credits
    )

    final_tax = money(
        max(
            Decimal("0"),
            tax_before_credits
            - prior_provisional_payments
            - isr_withholding
            - credits,
        )
    )

    steps = [
        ISRCalculationStep(
            code="taxable_base",
            formula=taxable_base_formula,
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
    ]

    if prior_provisional_payments != Decimal("0.00"):
        steps.append(
            ISRCalculationStep(
                code="prior_provisional_payments",
                formula="declared_prior_provisional_payments",
                result=prior_provisional_payments,
            )
        )

    if isr_withholding != Decimal("0.00"):
        steps.append(
            ISRCalculationStep(
                code="isr_withholding",
                formula="declared_isr_withholding",
                result=isr_withholding,
            )
        )

    steps.append(
        ISRCalculationStep(
            code="final_tax",
            formula=(
                "max(0, tax_before_credits - "
                "prior_provisional_payments - "
                "isr_withholding - credits)"
            ),
            result=final_tax,
        )
    )

    return ISRCalculationResult(
        fiscal_year=calculation_input.fiscal_year,
        period=calculation_input.period,
        taxable_base=taxable_base,
        selected_lower_limit=bracket.lower_limit,
        selected_upper_limit=bracket.upper_limit,
        fixed_fee=bracket.fixed_fee,
        rate_percent=bracket.rate_percent,
        tax_before_credits=tax_before_credits,
        prior_provisional_payments=prior_provisional_payments,
        isr_withholding=isr_withholding,
        credits=credits,
        final_tax=final_tax,
        normative_ref=tariff.normative_ref,
        tariff_version=tariff.version,
        source_reference=tariff.source_reference,
        steps=steps,
    )
