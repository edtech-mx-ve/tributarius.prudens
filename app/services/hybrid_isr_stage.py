from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.domain.isr import ISRCalculationInput, ISRCalculationResult, ISRPeriod, ISRTariff
from app.domain.orchestration import StageStatus
from app.domain.query import QueryIntent
from app.domain.rules import RuleEvaluationResult
from app.services.rbr_isr_bridge import (
    ISR_PROFESSIONAL_TRIGGER,
    RBRISRBridgeError,
    calculate_isr_from_rbr,
)
from calculators.isr import ISRCalculationError, calculate_isr
from calculators.isr_tariff_registry import ISRTariffRegistry, ISRTariffRegistryError


@dataclass(frozen=True)
class ISRStageOutcome:
    result: ISRCalculationResult | None
    status: StageStatus
    detail: str
    requires_human_review: bool


def merge_structured_isr_facts(
    facts: Mapping[str, Any],
    isr_input: ISRCalculationInput | None,
) -> dict[str, Any]:
    """Integra datos fiscales estructurados sin sobreescribir hechos ya extraídos."""
    merged = dict(facts)
    if isr_input is None:
        return merged

    structured = {
        "fiscal_year": isr_input.fiscal_year,
        "isr_period": isr_input.period.value,
        "gross_income": isr_input.gross_income,
        "exempt_income": isr_input.exempt_income,
        "authorized_deductions": isr_input.authorized_deductions,
        "credits": isr_input.credits,
    }
    for name, value in structured.items():
        merged.setdefault(name, value)
    return merged


def _rbr_authorizes_isr(rule_result: RuleEvaluationResult) -> bool:
    return any(
        conclusion.conclusion_code == ISR_PROFESSIONAL_TRIGGER
        for conclusion in rule_result.matched_rules
    )


def _coerce_period(value: object) -> ISRPeriod:
    if isinstance(value, ISRPeriod):
        return value
    try:
        return ISRPeriod(str(value))
    except ValueError as exc:
        raise RBRISRBridgeError(
            "No existe una periodicidad ISR válida para seleccionar la tarifa."
        ) from exc


def _select_tariff(
    *,
    facts: Mapping[str, Any],
    tariff_registry: ISRTariffRegistry | None,
    legacy_tariff: ISRTariff | None,
) -> ISRTariff:
    if tariff_registry is not None:
        fiscal_year_raw = facts.get("fiscal_year")
        period_raw = facts.get("isr_period")
        if fiscal_year_raw is None or period_raw is None:
            raise RBRISRBridgeError(
                "Faltan ejercicio fiscal o periodicidad para seleccionar la tarifa ISR."
            )
        if isinstance(fiscal_year_raw, bool):
            raise RBRISRBridgeError("El ejercicio fiscal para la tarifa ISR es inválido.")
        try:
            fiscal_year = int(fiscal_year_raw)
        except (TypeError, ValueError) as exc:
            raise RBRISRBridgeError(
                "El ejercicio fiscal para la tarifa ISR es inválido."
            ) from exc
        period = _coerce_period(period_raw)
        return tariff_registry.select_for_fiscal_use(fiscal_year, period)

    if legacy_tariff is not None:
        return legacy_tariff

    raise RBRISRBridgeError("No hay una tarifa ISR disponible para el cálculo.")


def run_isr_stage(
    *,
    intent: QueryIntent,
    requires_clarification: bool,
    rule_result: RuleEvaluationResult,
    facts: Mapping[str, Any],
    structured_input: ISRCalculationInput | None,
    applicable_normative_refs: set[str],
    tariff_registry: ISRTariffRegistry | None = None,
    legacy_tariff: ISRTariff | None = None,
) -> ISRStageOutcome:
    """Coordina RBR → selección fiscal segura → cálculo ISR determinístico."""
    if intent != QueryIntent.CALCULATE_ISR:
        return ISRStageOutcome(
            result=None,
            status=StageStatus.SKIPPED,
            detail="La intención principal no requiere cálculo ISR.",
            requires_human_review=False,
        )

    if requires_clarification:
        return ISRStageOutcome(
            result=None,
            status=StageStatus.SKIPPED,
            detail="Cálculo omitido: faltan datos requeridos.",
            requires_human_review=True,
        )

    if not _rbr_authorizes_isr(rule_result):
        if tariff_registry is not None:
            return ISRStageOutcome(
                result=None,
                status=StageStatus.SKIPPED,
                detail="Cálculo omitido: el RBR no determinó obligación de cálculo ISR.",
                requires_human_review=True,
            )

        # Compatibilidad controlada con el contrato histórico del orquestador.
        # Solo aplica cuando NO existe registro fiscal seguro configurado.
        if structured_input is None or legacy_tariff is None:
            return ISRStageOutcome(
                result=None,
                status=StageStatus.SKIPPED,
                detail="Cálculo omitido: el RBR no determinó obligación de cálculo ISR.",
                requires_human_review=True,
            )
        if structured_input.normative_ref not in applicable_normative_refs:
            return ISRStageOutcome(
                result=None,
                status=StageStatus.SKIPPED,
                detail="Cálculo omitido: referencia normativa no validada.",
                requires_human_review=True,
            )
        try:
            legacy_result = calculate_isr(structured_input, legacy_tariff)
        except ISRCalculationError:
            return ISRStageOutcome(
                result=None,
                status=StageStatus.DEGRADED,
                detail="El cálculo ISR legado fue rechazado por validación determinística.",
                requires_human_review=True,
            )
        return ISRStageOutcome(
            result=legacy_result,
            status=StageStatus.COMPLETED,
            detail=(
                "Cálculo ISR ejecutado por compatibilidad controlada del "
                "orquestador legado."
            ),
            requires_human_review=False,
        )

    merged_facts = merge_structured_isr_facts(facts, structured_input)

    try:
        tariff = _select_tariff(
            facts=merged_facts,
            tariff_registry=tariff_registry,
            legacy_tariff=legacy_tariff,
        )
        if tariff.normative_ref not in applicable_normative_refs:
            return ISRStageOutcome(
                result=None,
                status=StageStatus.SKIPPED,
                detail="Cálculo omitido: fundamento de la tarifa ISR no validado.",
                requires_human_review=True,
            )
        result = calculate_isr_from_rbr(rule_result, merged_facts, tariff)
    except (RBRISRBridgeError, ISRTariffRegistryError, ISRCalculationError):
        return ISRStageOutcome(
            result=None,
            status=StageStatus.DEGRADED,
            detail="El cálculo ISR fue rechazado por validación determinística.",
            requires_human_review=True,
        )

    if result is None:
        return ISRStageOutcome(
            result=None,
            status=StageStatus.SKIPPED,
            detail="Cálculo omitido: el RBR no habilitó la ejecución ISR.",
            requires_human_review=True,
        )

    return ISRStageOutcome(
        result=result,
        status=StageStatus.COMPLETED,
        detail="Cálculo ISR ejecutado por RBR y motor determinístico.",
        requires_human_review=False,
    )
