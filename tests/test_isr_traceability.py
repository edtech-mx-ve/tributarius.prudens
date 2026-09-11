from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.domain.isr import (
    ISRBracket,
    ISRCalculationInput,
    ISRPeriod,
    ISRTariff,
    ISRTariffLegalMetadata,
    ISRTariffScope,
)
from app.domain.normative import NormativeValidityStatus
from app.domain.rules import RuleConclusion, RuleEvaluationResult
from app.services.isr_traceability import (
    ISRTraceabilityError,
    build_isr_calculation_trace,
    verify_isr_calculation_trace,
)
from calculators.isr import calculate_isr

NORM_REF = "lisr:articulo_152"


def _tariff(
    *,
    validity: NormativeValidityStatus = NormativeValidityStatus.VERIFIED_IN_FORCE,
) -> ISRTariff:
    return ISRTariff(
        schema_version="1.0",
        version="TEST-2026",
        fiscal_year=2026,
        period=ISRPeriod.ANNUAL,
        normative_ref=NORM_REF,
        source_reference="FIXTURE_ONLY",
        verified=True,
        legal_metadata=ISRTariffLegalMetadata(
            source_document_id="lisr",
            legal_basis_refs=[NORM_REF],
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 12, 31),
            validity_status=validity,
        ),
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


def _input() -> ISRCalculationInput:
    return ISRCalculationInput(
        fiscal_year=2026,
        period=ISRPeriod.ANNUAL,
        gross_income=Decimal("20000"),
        exempt_income=Decimal("1000"),
        authorized_deductions=Decimal("2000"),
        credits=Decimal("100"),
        normative_ref=NORM_REF,
    )


def _rules(*, authorized: bool = True) -> RuleEvaluationResult:
    matched: list[RuleConclusion] = []
    if authorized:
        matched.append(
            RuleConclusion(
                rule_id="ISR_PROFESSIONAL_PAYMENT_002",
                version="1.0.0",
                conclusion_code="isr_professional_payment_obligation",
                conclusion="Existe obligación de pago ISR.",
                normative_refs=["lisr:articulo_100"],
                source_refs=["LISR, artículo 100"],
                requires_human_review=False,
            )
        )
    return RuleEvaluationResult(
        matched_rules=matched,
        traces=[],
        derivations=[],
        requires_human_review=False,
    )


def test_trace_reconstructs_mathematical_and_legal_chain() -> None:
    calculation_input = _input()
    tariff = _tariff()
    result = calculate_isr(calculation_input, tariff)

    trace = build_isr_calculation_trace(
        calculation_input,
        result,
        tariff,
        _rules(),
    )
    verification = verify_isr_calculation_trace(trace)

    assert trace.input.gross_income == Decimal("20000")
    assert trace.bracket.lower_limit == Decimal("10000.01")
    assert trace.legal.normative_ref == NORM_REF
    assert trace.legal.tariff_version == "TEST-2026"
    assert trace.authorization.rule_id == "ISR_PROFESSIONAL_PAYMENT_002"
    assert [step.code for step in trace.steps] == [
        "taxable_base",
        "excess_over_lower_limit",
        "marginal_tax",
        "tax_before_credits",
        "final_tax",
    ]
    assert verification.mathematically_consistent is True
    assert verification.legally_linked is True
    assert verification.rbr_authorized is True
    assert verification.verified is True


def test_trace_detects_mathematical_tampering() -> None:
    calculation_input = _input()
    tariff = _tariff()
    result = calculate_isr(calculation_input, tariff)
    trace = build_isr_calculation_trace(
        calculation_input,
        result,
        tariff,
        _rules(),
    )

    tampered = trace.model_copy(update={"final_tax": Decimal("999999")})
    verification = verify_isr_calculation_trace(tampered)

    assert verification.mathematically_consistent is False
    assert verification.verified is False


def test_trace_requires_rbr_authorization() -> None:
    calculation_input = _input()
    tariff = _tariff()
    result = calculate_isr(calculation_input, tariff)

    with pytest.raises(ISRTraceabilityError, match="autorice"):
        build_isr_calculation_trace(
            calculation_input,
            result,
            tariff,
            _rules(authorized=False),
        )


def test_trace_marks_unknown_tariff_validity_as_not_legally_verified() -> None:
    calculation_input = _input()
    tariff = _tariff(validity=NormativeValidityStatus.UNKNOWN)
    result = calculate_isr(calculation_input, tariff)
    trace = build_isr_calculation_trace(
        calculation_input,
        result,
        tariff,
        _rules(),
    )

    verification = verify_isr_calculation_trace(trace)

    assert verification.mathematically_consistent is True
    assert verification.legally_linked is False
    assert verification.verified is False


def test_trace_rejects_mismatched_tariff_version() -> None:
    calculation_input = _input()
    tariff = _tariff()
    result = calculate_isr(calculation_input, tariff)
    mismatched_tariff = tariff.model_copy(update={"version": "OTHER"})

    with pytest.raises(ISRTraceabilityError, match="versión"):
        build_isr_calculation_trace(
            calculation_input,
            result,
            mismatched_tariff,
            _rules(),
        )

def test_trace_supports_declared_year_to_month_base_and_article_106_subtractions() -> None:
    normative_ref = "lisr:articulo_106"

    tariff = ISRTariff(
        schema_version="1.0",
        version="TEST-2026-M09",
        fiscal_year=2026,
        period=ISRPeriod.MONTHLY,
        month=9,
        tariff_scope=ISRTariffScope.YEAR_TO_MONTH,
        normative_ref=normative_ref,
        source_reference="RMF Anexo 8 test",
        verified=True,
        legal_metadata=ISRTariffLegalMetadata(
            source_document_id="rmf_2026",
            legal_basis_refs=[normative_ref],
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 12, 31),
            validity_status=NormativeValidityStatus.VERIFIED_IN_FORCE,
        ),
        brackets=[
            ISRBracket(
                lower_limit=Decimal("7601.32"),
                upper_limit=Decimal("64516.59"),
                fixed_fee=Decimal("145.98"),
                rate_percent=Decimal("6.40"),
            ),
        ],
    )

    calculation_input = ISRCalculationInput(
        fiscal_year=2026,
        period=ISRPeriod.MONTHLY,
        taxable_base=Decimal("35000.00"),
        prior_provisional_payments=Decimal("1200.00"),
        isr_withholding=Decimal("200.00"),
        normative_ref=normative_ref,
    )

    result = calculate_isr(calculation_input, tariff)

    trace = build_isr_calculation_trace(
        calculation_input,
        result,
        tariff,
        _rules(),
    )
    verification = verify_isr_calculation_trace(trace)

    assert trace.input.gross_income is None
    assert trace.input.taxable_base == Decimal("35000.00")
    assert (
        trace.input.prior_provisional_payments
        == Decimal("1200.00")
    )
    assert trace.input.isr_withholding == Decimal("200.00")

    assert trace.taxable_base == Decimal("35000.00")
    assert trace.tax_before_credits == Decimal("1899.50")
    assert trace.final_tax == Decimal("499.50")

    assert verification.mathematically_consistent is True
    assert verification.legally_linked is True
    assert verification.rbr_authorized is True
    assert verification.verified is True
