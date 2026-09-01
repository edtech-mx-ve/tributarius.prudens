from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.domain.isr import ISRCalculationInput, ISRPeriod
from app.domain.normative import NormativeValidityStatus
from calculators.isr import calculate_isr
from calculators.isr_tariff_registry import (
    ISRTariffRegistryError,
    load_isr_tariff_registry,
    require_tariff_legal_metadata,
)

CONTROLLED_TARIFF = Path(
    "calculators/tariffs/isr_annual_lisr_article_152_2024.json"
)


def _verified_annual_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "version": "INTEGRAL-2026-ANNUAL",
        "fiscal_year": 2026,
        "period": "annual",
        "normative_ref": "lisr:articulo_152",
        "source_reference": "CONTROLLED_INTEGRAL_TEST_SOURCE",
        "verified": True,
        "legal_metadata": {
            "source_document_id": "lisr",
            "legal_basis_refs": ["lisr:articulo_152"],
            "publication_date": "2025-12-31",
            "effective_from": "2026-01-01",
            "effective_to": "2026-12-31",
            "validity_status": "verified_in_force",
            "validity_scope": "fiscal_year",
            "validity_basis": "fiscal_year_rule",
            "validity_verified_at": "2026-01-01",
            "official_source": "CONTROLLED_INTEGRAL_TEST_SOURCE",
        },
        "brackets": [
            {
                "lower_limit": "0.00",
                "upper_limit": "100000.00",
                "fixed_fee": "0.00",
                "rate_percent": "10.00",
            },
            {
                "lower_limit": "100000.01",
                "upper_limit": None,
                "fixed_fee": "10000.00",
                "rate_percent": "20.00",
            },
        ],
    }


def _write_tariff(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "isr_integral_2026_annual.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_integral_registry_selects_only_exact_verified_tariff(tmp_path: Path) -> None:
    path = _write_tariff(tmp_path, _verified_annual_payload())
    registry = load_isr_tariff_registry([path])

    tariff = registry.select_for_fiscal_use(2026, ISRPeriod.ANNUAL)
    metadata = require_tariff_legal_metadata(tariff)

    assert tariff.version == "INTEGRAL-2026-ANNUAL"
    assert tariff.fiscal_year == 2026
    assert tariff.period == ISRPeriod.ANNUAL
    assert metadata.validity_status == NormativeValidityStatus.VERIFIED_IN_FORCE
    assert metadata.effective_from is not None


def test_integral_selection_fails_closed_for_wrong_year(tmp_path: Path) -> None:
    path = _write_tariff(tmp_path, _verified_annual_payload())
    registry = load_isr_tariff_registry([path])

    with pytest.raises(ISRTariffRegistryError):
        registry.select_for_fiscal_use(2025, ISRPeriod.ANNUAL)


def test_integral_selection_fails_closed_for_wrong_period(tmp_path: Path) -> None:
    path = _write_tariff(tmp_path, _verified_annual_payload())
    registry = load_isr_tariff_registry([path])

    with pytest.raises(ISRTariffRegistryError):
        registry.select_for_fiscal_use(2026, ISRPeriod.MONTHLY)


def test_integral_controlled_tariff_is_evidence_but_not_fiscal_authority() -> None:
    registry = load_isr_tariff_registry([CONTROLLED_TARIFF])

    evidence = registry.get(2024, ISRPeriod.ANNUAL)
    metadata = require_tariff_legal_metadata(evidence)

    assert evidence.version == "LISR-ART152-CORPUS-2024"
    assert metadata.validity_status == NormativeValidityStatus.UNKNOWN

    with pytest.raises(ISRTariffRegistryError, match="vigencia no está verificada"):
        registry.select_for_fiscal_use(2024, ISRPeriod.ANNUAL)


def test_integral_verified_selection_drives_reproducible_calculation(
    tmp_path: Path,
) -> None:
    path = _write_tariff(tmp_path, _verified_annual_payload())
    registry = load_isr_tariff_registry([path])
    tariff = registry.select_for_fiscal_use(2026, ISRPeriod.ANNUAL)

    result = calculate_isr(
        ISRCalculationInput(
            fiscal_year=2026,
            period=ISRPeriod.ANNUAL,
            gross_income=Decimal("150000.00"),
            exempt_income=Decimal("10000.00"),
            authorized_deductions=Decimal("10000.00"),
            credits=Decimal("500.00"),
            normative_ref="lisr:articulo_152",
        ),
        tariff,
    )

    assert result.taxable_base == Decimal("130000.00")
    assert result.selected_lower_limit == Decimal("100000.01")
    assert result.fixed_fee == Decimal("10000.00")
    assert result.rate_percent == Decimal("20.00")
    assert result.tax_before_credits == Decimal("16000.00")
    assert result.final_tax == Decimal("15500.00")


def test_integral_calculation_preserves_normative_traceability(tmp_path: Path) -> None:
    path = _write_tariff(tmp_path, _verified_annual_payload())
    registry = load_isr_tariff_registry([path])
    tariff = registry.select_for_fiscal_use(2026, ISRPeriod.ANNUAL)

    result = calculate_isr(
        ISRCalculationInput(
            fiscal_year=2026,
            period=ISRPeriod.ANNUAL,
            gross_income=Decimal("50000.00"),
            normative_ref="lisr:articulo_152",
        ),
        tariff,
    )

    assert result.normative_ref == "lisr:articulo_152"
    assert result.tariff_version == "INTEGRAL-2026-ANNUAL"
    assert result.source_reference == "CONTROLLED_INTEGRAL_TEST_SOURCE"
    assert [step.code for step in result.steps] == [
        "taxable_base",
        "excess_over_lower_limit",
        "marginal_tax",
        "tax_before_credits",
        "final_tax",
    ]


def test_integral_calculation_is_deterministic_for_same_input(tmp_path: Path) -> None:
    path = _write_tariff(tmp_path, _verified_annual_payload())
    registry = load_isr_tariff_registry([path])
    tariff = registry.select_for_fiscal_use(2026, ISRPeriod.ANNUAL)
    calculation_input = ISRCalculationInput(
        fiscal_year=2026,
        period=ISRPeriod.ANNUAL,
        gross_income=Decimal("75000.00"),
        exempt_income=Decimal("5000.00"),
        authorized_deductions=Decimal("2500.00"),
        credits=Decimal("250.00"),
        normative_ref="lisr:articulo_152",
    )

    first = calculate_isr(calculation_input, tariff)
    second = calculate_isr(calculation_input, tariff)

    assert first == second
