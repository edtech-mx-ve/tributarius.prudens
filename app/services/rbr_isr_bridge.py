from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain.isr import ISRCalculationInput, ISRCalculationResult, ISRPeriod, ISRTariff
from app.domain.rules import RuleEvaluationResult
from calculators.isr import calculate_isr

ISR_PROFESSIONAL_TRIGGER = "isr_professional_payment_obligation"


class RBRISRBridgeError(ValueError):
    """Error controlado al convertir una conclusión RBR en cálculo ISR."""


def _has_trigger(rule_result: RuleEvaluationResult) -> bool:
    return any(
        conclusion.conclusion_code == ISR_PROFESSIONAL_TRIGGER
        for conclusion in rule_result.matched_rules
    )


def _required_fact(facts: Mapping[str, Any], name: str) -> Any:
    if name not in facts:
        raise RBRISRBridgeError(
            f"El RBR activó el cálculo ISR, pero falta el hecho requerido '{name}'."
        )
    return facts[name]


def _decimal_fact(facts: Mapping[str, Any], name: str, *, default: str | None = None) -> Decimal:
    value = facts.get(name, default)
    if value is None:
        raise RBRISRBridgeError(
            f"El RBR activó el cálculo ISR, pero falta el hecho requerido '{name}'."
        )
    if isinstance(value, bool):
        raise RBRISRBridgeError(f"El hecho '{name}' no contiene un importe válido.")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise RBRISRBridgeError(
            f"El hecho '{name}' no contiene un importe decimal válido."
        ) from exc


def build_isr_input_from_rbr(
    rule_result: RuleEvaluationResult,
    facts: Mapping[str, Any],
    tariff: ISRTariff,
) -> ISRCalculationInput | None:
    """Construye entrada ISR solo cuando el RBR determinó obligación de pago."""
    if not _has_trigger(rule_result):
        return None

    fiscal_year_raw = _required_fact(facts, "fiscal_year")
    if isinstance(fiscal_year_raw, bool):
        raise RBRISRBridgeError("El hecho 'fiscal_year' no contiene un ejercicio válido.")
    try:
        fiscal_year = int(fiscal_year_raw)
    except (TypeError, ValueError) as exc:
        raise RBRISRBridgeError(
            "El hecho 'fiscal_year' no contiene un ejercicio válido."
        ) from exc

    period_raw = _required_fact(facts, "isr_period")
    try:
        period = ISRPeriod(str(period_raw))
    except ValueError as exc:
        raise RBRISRBridgeError(
            "El hecho 'isr_period' no contiene una periodicidad ISR soportada."
        ) from exc

    try:
        return ISRCalculationInput(
            fiscal_year=fiscal_year,
            period=period,
            gross_income=_decimal_fact(facts, "gross_income"),
            exempt_income=_decimal_fact(facts, "exempt_income", default="0"),
            authorized_deductions=_decimal_fact(
                facts, "authorized_deductions", default="0"
            ),
            credits=_decimal_fact(facts, "credits", default="0"),
            normative_ref=tariff.normative_ref,
        )
    except RBRISRBridgeError:
        raise
    except ValueError as exc:
        raise RBRISRBridgeError(
            "Los hechos RBR no permiten construir una entrada ISR válida."
        ) from exc


def calculate_isr_from_rbr(
    rule_result: RuleEvaluationResult,
    facts: Mapping[str, Any],
    tariff: ISRTariff,
) -> ISRCalculationResult | None:
    """Ejecuta el motor determinístico únicamente después del disparador RBR."""
    calculation_input = build_isr_input_from_rbr(rule_result, facts, tariff)
    if calculation_input is None:
        return None
    return calculate_isr(calculation_input, tariff)
