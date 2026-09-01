from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.domain.isr import (
    ISRBracket,
    ISRCalculationInput,
    ISRPeriod,
    ISRTariff,
    ISRTariffLegalMetadata,
)
from app.domain.normative import NormativeValidityStatus
from app.domain.orchestration import StageStatus
from app.domain.query import QueryIntent
from app.domain.rules import RuleConclusion, RuleEvaluationResult
from app.services.hybrid_isr_stage import run_isr_stage
from calculators.isr_tariff_registry import ISRTariffRegistry

NORM_REF = "lisr:articulo_152"


def _rule_result(*, trigger: bool = True) -> RuleEvaluationResult:
    matched = []
    if trigger:
        matched.append(
            RuleConclusion(
                rule_id="ISR_PROFESSIONAL_PAYMENT_002",
                version="1.0.0",
                conclusion_code="isr_professional_payment_obligation",
                conclusion="Obligación ISR determinada por RBR.",
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


def _tariff(*, verified_in_force: bool = True) -> ISRTariff:
    return ISRTariff(
        schema_version="1.0",
        version="TEST-2026-ANNUAL",
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
            validity_status=(
                NormativeValidityStatus.VERIFIED_IN_FORCE
                if verified_in_force
                else NormativeValidityStatus.UNKNOWN
            ),
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


def _structured_input() -> ISRCalculationInput:
    return ISRCalculationInput(
        fiscal_year=2026,
        period=ISRPeriod.ANNUAL,
        gross_income=Decimal("20000"),
        exempt_income=Decimal("1000"),
        authorized_deductions=Decimal("2000"),
        credits=Decimal("100"),
        normative_ref=NORM_REF,
    )


def test_hybrid_isr_stage_executes_only_after_rbr_trigger() -> None:
    outcome = run_isr_stage(
        intent=QueryIntent.CALCULATE_ISR,
        requires_clarification=False,
        rule_result=_rule_result(),
        facts={"fiscal_year": 2026},
        structured_input=_structured_input(),
        applicable_normative_refs={NORM_REF},
        tariff_registry=ISRTariffRegistry([_tariff()]),
    )

    assert outcome.status == StageStatus.COMPLETED
    assert outcome.result is not None
    assert outcome.result.final_tax == Decimal("2300.00")
    assert outcome.requires_human_review is False


def test_hybrid_isr_stage_blocks_when_rbr_does_not_authorize() -> None:
    outcome = run_isr_stage(
        intent=QueryIntent.CALCULATE_ISR,
        requires_clarification=False,
        rule_result=_rule_result(trigger=False),
        facts={"fiscal_year": 2026},
        structured_input=_structured_input(),
        applicable_normative_refs={NORM_REF},
        tariff_registry=ISRTariffRegistry([_tariff()]),
    )

    assert outcome.status == StageStatus.SKIPPED
    assert outcome.result is None
    assert outcome.requires_human_review is True


def test_hybrid_isr_stage_uses_safe_tariff_selection() -> None:
    outcome = run_isr_stage(
        intent=QueryIntent.CALCULATE_ISR,
        requires_clarification=False,
        rule_result=_rule_result(),
        facts={"fiscal_year": 2026},
        structured_input=_structured_input(),
        applicable_normative_refs={NORM_REF},
        tariff_registry=ISRTariffRegistry([_tariff(verified_in_force=False)]),
    )

    assert outcome.status == StageStatus.DEGRADED
    assert outcome.result is None
    assert outcome.requires_human_review is True


def test_hybrid_isr_stage_rejects_unvalidated_tariff_basis() -> None:
    outcome = run_isr_stage(
        intent=QueryIntent.CALCULATE_ISR,
        requires_clarification=False,
        rule_result=_rule_result(),
        facts={"fiscal_year": 2026},
        structured_input=_structured_input(),
        applicable_normative_refs={"lisr:articulo_100"},
        tariff_registry=ISRTariffRegistry([_tariff()]),
    )

    assert outcome.status == StageStatus.SKIPPED
    assert outcome.result is None
    assert outcome.requires_human_review is True


def test_hybrid_isr_stage_preserves_clarification_gate() -> None:
    outcome = run_isr_stage(
        intent=QueryIntent.CALCULATE_ISR,
        requires_clarification=True,
        rule_result=_rule_result(),
        facts={"fiscal_year": 2026},
        structured_input=_structured_input(),
        applicable_normative_refs={NORM_REF},
        tariff_registry=ISRTariffRegistry([_tariff()]),
    )

    assert outcome.status == StageStatus.SKIPPED
    assert outcome.result is None
    assert outcome.requires_human_review is True


def test_hybrid_isr_stage_skips_non_isr_intent_without_review() -> None:
    outcome = run_isr_stage(
        intent=QueryIntent.KNOW_RIGHTS,
        requires_clarification=False,
        rule_result=_rule_result(),
        facts={"fiscal_year": 2026},
        structured_input=_structured_input(),
        applicable_normative_refs={NORM_REF},
        tariff_registry=ISRTariffRegistry([_tariff()]),
    )

    assert outcome.status == StageStatus.SKIPPED
    assert outcome.result is None
    assert outcome.requires_human_review is False
