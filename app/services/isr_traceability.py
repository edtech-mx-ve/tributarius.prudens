from __future__ import annotations

from decimal import Decimal

from app.domain.isr import ISRCalculationInput, ISRCalculationResult, ISRTariff
from app.domain.isr_trace import (
    ISRBracketTrace,
    ISRCalculationTrace,
    ISRInputTrace,
    ISRLegalTrace,
    ISRRuleAuthorizationTrace,
    ISRTraceVerification,
)
from app.domain.normative import NormativeValidityStatus
from app.domain.rules import RuleConclusion, RuleEvaluationResult
from app.services.rbr_isr_bridge import ISR_PROFESSIONAL_TRIGGER
from calculators.isr import HUNDRED, money


class ISRTraceabilityError(ValueError):
    """Error controlado de construcción o verificación de trazabilidad ISR."""


def _authorization(rule_result: RuleEvaluationResult) -> RuleConclusion:
    for conclusion in rule_result.matched_rules:
        if conclusion.conclusion_code == ISR_PROFESSIONAL_TRIGGER:
            return conclusion
    raise ISRTraceabilityError(
        "No existe una conclusión RBR que autorice el cálculo ISR."
    )


def _validate_links(
    calculation_input: ISRCalculationInput,
    result: ISRCalculationResult,
    tariff: ISRTariff,
) -> None:
    if calculation_input.fiscal_year != result.fiscal_year:
        raise ISRTraceabilityError("El ejercicio fiscal no coincide con el resultado.")
    if calculation_input.period != result.period:
        raise ISRTraceabilityError("La periodicidad no coincide con el resultado.")
    if calculation_input.normative_ref != result.normative_ref:
        raise ISRTraceabilityError("La entrada y el resultado no comparten fundamento.")
    if result.normative_ref != tariff.normative_ref:
        raise ISRTraceabilityError("El resultado y la tarifa no comparten fundamento.")
    if result.tariff_version != tariff.version:
        raise ISRTraceabilityError("La versión de tarifa no coincide con el resultado.")
    if result.source_reference != tariff.source_reference:
        raise ISRTraceabilityError("La fuente de tarifa no coincide con el resultado.")


def build_isr_calculation_trace(
    calculation_input: ISRCalculationInput,
    result: ISRCalculationResult,
    tariff: ISRTariff,
    rule_result: RuleEvaluationResult,
) -> ISRCalculationTrace:
    """Construye la cadena entrada → RBR → tarifa → operaciones → resultado."""
    _validate_links(calculation_input, result, tariff)
    authorization = _authorization(rule_result)

    legal_metadata = tariff.legal_metadata
    source_document_id = None
    legal_basis_refs: list[str] = []
    validity_status = NormativeValidityStatus.UNKNOWN
    if legal_metadata is not None:
        source_document_id = legal_metadata.source_document_id
        legal_basis_refs = list(legal_metadata.legal_basis_refs)
        validity_status = legal_metadata.validity_status

    return ISRCalculationTrace(
        input=ISRInputTrace(
            fiscal_year=calculation_input.fiscal_year,
            period=calculation_input.period,
            gross_income=calculation_input.gross_income,
            exempt_income=calculation_input.exempt_income,
            authorized_deductions=calculation_input.authorized_deductions,
            credits=calculation_input.credits,
            normative_ref=calculation_input.normative_ref,
        ),
        bracket=ISRBracketTrace(
            lower_limit=result.selected_lower_limit,
            upper_limit=result.selected_upper_limit,
            fixed_fee=result.fixed_fee,
            rate_percent=result.rate_percent,
        ),
        steps=list(result.steps),
        legal=ISRLegalTrace(
            normative_ref=result.normative_ref,
            tariff_version=result.tariff_version,
            source_reference=result.source_reference,
            source_document_id=source_document_id,
            legal_basis_refs=legal_basis_refs,
            validity_status=validity_status,
        ),
        authorization=ISRRuleAuthorizationTrace(
            rule_id=authorization.rule_id,
            version=authorization.version,
            conclusion_code=authorization.conclusion_code,
            normative_refs=list(authorization.normative_refs),
            source_refs=list(authorization.source_refs),
        ),
        taxable_base=result.taxable_base,
        tax_before_credits=result.tax_before_credits,
        final_tax=result.final_tax,
    )


def verify_isr_calculation_trace(trace: ISRCalculationTrace) -> ISRTraceVerification:
    """Reejecuta aritmética esencial y verifica enlaces jurídicos sin LLM."""
    taxable_base = money(
        trace.input.gross_income
        - trace.input.exempt_income
        - trace.input.authorized_deductions
    )
    excess = money(taxable_base - trace.bracket.lower_limit)
    marginal_tax = money(excess * trace.bracket.rate_percent / HUNDRED)
    tax_before_credits = money(trace.bracket.fixed_fee + marginal_tax)
    final_tax = money(
        max(Decimal("0"), tax_before_credits - trace.input.credits)
    )

    mathematically_consistent = (
        taxable_base == trace.taxable_base
        and tax_before_credits == trace.tax_before_credits
        and final_tax == trace.final_tax
    )
    legally_linked = (
        trace.input.normative_ref == trace.legal.normative_ref
        and trace.legal.normative_ref in trace.legal.legal_basis_refs
        and trace.legal.validity_status == NormativeValidityStatus.VERIFIED_IN_FORCE
    )
    rbr_authorized = (
        trace.authorization.conclusion_code == ISR_PROFESSIONAL_TRIGGER
        and bool(trace.authorization.rule_id)
        and bool(trace.authorization.normative_refs)
    )

    return ISRTraceVerification(
        mathematically_consistent=mathematically_consistent,
        legally_linked=legally_linked,
        rbr_authorized=rbr_authorized,
        verified=mathematically_consistent and legally_linked and rbr_authorized,
    )
