from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from app.domain.isr import ISRPeriod
from app.domain.orchestration import StageStatus
from app.domain.query import QueryIntent
from app.services.hybrid_isr_stage import run_isr_stage
from app.services.primary_rbs_inventory import (
    load_current_production_rule_set,
)
from app.services.rule_engine import evaluate_rules
from app.services.runtime_factory import (
    load_runtime_isr_tariff_registry,
)

ROOT = Path(__file__).resolve().parents[1]


def _facts() -> dict[str, object]:
    return {
        "taxpayer_type": "individual",
        "income_type": "independent_professional_service",
        "fiscal_year": 2026,
        "isr_period": "monthly",
        "isr_month": 9,
        "taxable_base": "35000.00",
        "taxable_base_scope": "year_to_month",
        "prior_provisional_payments": "1200.00",
        "isr_withholding": "200.00",
    }


def _rule_result(facts: dict[str, object]):
    rule_set = load_current_production_rule_set(
        ROOT / "app/resources/current_rbs_inventory.json",
        ROOT / "rules/production",
    )
    return evaluate_rules(
        rule_set,
        facts,
        {
            "lisr:articulo_100",
            "lisr:articulo_106",
        },
    )


def test_runtime_registry_loads_exactly_twelve_2026_months() -> None:
    registry = load_runtime_isr_tariff_registry()

    assert len(registry.tariffs) == 12
    assert {
        tariff.month
        for tariff in registry.tariffs
    } == set(range(1, 13))

    assert all(
        tariff.fiscal_year == 2026
        and tariff.period is ISRPeriod.MONTHLY
        and tariff.tariff_scope.value == "year_to_month"
        and tariff.normative_ref == "lisr:articulo_106"
        for tariff in registry.tariffs
    )


def test_runtime_stage_selects_exact_september_tariff() -> None:
    facts = _facts()
    registry = load_runtime_isr_tariff_registry()

    outcome = run_isr_stage(
        intent=QueryIntent.CALCULATE_ISR,
        requires_clarification=False,
        rule_result=_rule_result(facts),
        facts=facts,
        structured_input=None,
        applicable_normative_refs={
            "lisr:articulo_100",
            "lisr:articulo_106",
        },
        tariff_registry=registry,
    )

    assert outcome.status is StageStatus.COMPLETED
    assert outcome.requires_human_review is False
    assert outcome.rbr_authorized is True

    assert outcome.tariff is not None
    assert outcome.tariff.month == 9
    assert outcome.tariff.version == (
        "RMF-ANEXO8-2026-ART106-M09"
    )
    assert outcome.tariff.tariff_scope.value == "year_to_month"

    assert outcome.result is not None
    assert outcome.result.taxable_base == Decimal("35000.00")

    assert outcome.result.tax_before_credits == Decimal(
        "1899.50"
    )

    assert (
        outcome.result.prior_provisional_payments
        == Decimal("1200.00")
    )

    assert outcome.result.isr_withholding == Decimal(
        "200.00"
    )

    assert outcome.result.final_tax == Decimal(
        "499.50"
    )

    assert outcome.calculation_input is not None

    assert (
        outcome.calculation_input.prior_provisional_payments
        == Decimal("1200.00")
    )

    assert (
        outcome.calculation_input.isr_withholding
        == Decimal("200.00")
    )

    assert [
        step.code
        for step in outcome.result.steps
    ] == [
        "taxable_base",
        "excess_over_lower_limit",
        "marginal_tax",
        "tax_before_credits",
        "prior_provisional_payments",
        "isr_withholding",
        "final_tax",
    ]

    assert outcome.result.steps[-1].formula == (
        "max(0, tax_before_credits - "
        "prior_provisional_payments - "
        "isr_withholding - credits)"
    )


def test_runtime_stage_fails_closed_when_month_is_missing() -> None:
    facts = _facts()
    facts.pop("isr_month")

    outcome = run_isr_stage(
        intent=QueryIntent.CALCULATE_ISR,
        requires_clarification=False,
        rule_result=_rule_result(facts),
        facts=facts,
        structured_input=None,
        applicable_normative_refs={
            "lisr:articulo_100",
            "lisr:articulo_106",
        },
        tariff_registry=load_runtime_isr_tariff_registry(),
    )

    assert outcome.result is None
    assert outcome.status is StageStatus.DEGRADED
    assert outcome.requires_human_review is True


def test_runtime_stage_fails_closed_for_invalid_month() -> None:
    facts = _facts()
    facts["isr_month"] = 13

    outcome = run_isr_stage(
        intent=QueryIntent.CALCULATE_ISR,
        requires_clarification=False,
        rule_result=_rule_result(facts),
        facts=facts,
        structured_input=None,
        applicable_normative_refs={
            "lisr:articulo_100",
            "lisr:articulo_106",
        },
        tariff_registry=load_runtime_isr_tariff_registry(),
    )

    assert outcome.result is None
    assert outcome.status is StageStatus.DEGRADED
    assert outcome.requires_human_review is True
