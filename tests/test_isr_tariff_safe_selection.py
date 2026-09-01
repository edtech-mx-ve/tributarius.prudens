from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.domain.isr import ISRPeriod
from calculators.isr_tariff_registry import (
    ISRTariffRegistryError,
    load_isr_tariff_registry,
)

CONTROLLED_TARIFF = Path(
    "calculators/tariffs/isr_annual_lisr_article_152_2024.json"
)


def _verified_payload(
    *, fiscal_year: int, period: str, effective_from: str | None = "2026-01-01"
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "version": f"SAFE-{fiscal_year}-{period}",
        "fiscal_year": fiscal_year,
        "period": period,
        "normative_ref": "lisr:articulo_152",
        "source_reference": "CONTROLLED_TEST_SOURCE",
        "verified": True,
        "legal_metadata": {
            "source_document_id": "lisr",
            "legal_basis_refs": ["lisr:articulo_152"],
            "publication_date": None,
            "effective_from": effective_from,
            "effective_to": None,
            "validity_status": "verified_in_force",
            "validity_scope": "fiscal_year",
            "validity_basis": "fiscal_year_rule",
            "validity_verified_at": "2026-01-01",
            "official_source": "CONTROLLED_TEST_SOURCE",
        },
        "brackets": [{
            "lower_limit": "0.01",
            "upper_limit": None,
            "fixed_fee": "0.00",
            "rate_percent": "10.00",
        }],
    }


def _write(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_safe_selection_requires_exact_year_and_period(tmp_path: Path) -> None:
    annual = _write(
        tmp_path / "annual.json",
        _verified_payload(fiscal_year=2026, period="annual"),
    )
    monthly = _write(
        tmp_path / "monthly.json",
        _verified_payload(fiscal_year=2026, period="monthly"),
    )
    registry = load_isr_tariff_registry([annual, monthly])

    selected = registry.select_for_fiscal_use(2026, ISRPeriod.ANNUAL)

    assert selected.fiscal_year == 2026
    assert selected.period == ISRPeriod.ANNUAL
    assert selected.version == "SAFE-2026-annual"


def test_safe_selection_never_falls_back_to_another_year(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "annual.json",
        _verified_payload(fiscal_year=2026, period="annual"),
    )
    registry = load_isr_tariff_registry([path])

    with pytest.raises(ISRTariffRegistryError, match="No existe una tarifa ISR verificada"):
        registry.select_for_fiscal_use(2025, ISRPeriod.ANNUAL)


def test_safe_selection_never_falls_back_to_another_period(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "monthly.json",
        _verified_payload(fiscal_year=2026, period="monthly"),
    )
    registry = load_isr_tariff_registry([path])

    with pytest.raises(ISRTariffRegistryError, match="No existe una tarifa ISR verificada"):
        registry.select_for_fiscal_use(2026, ISRPeriod.ANNUAL)


def test_safe_selection_rejects_unknown_validity_from_controlled_tariff() -> None:
    registry = load_isr_tariff_registry([CONTROLLED_TARIFF])

    with pytest.raises(ISRTariffRegistryError, match="vigencia no está verificada"):
        registry.select_for_fiscal_use(2024, ISRPeriod.ANNUAL)


def test_safe_selection_preserves_controlled_tariff_for_evidence_use() -> None:
    registry = load_isr_tariff_registry([CONTROLLED_TARIFF])

    tariff = registry.get(2024, ISRPeriod.ANNUAL)

    assert tariff.version == "LISR-ART152-CORPUS-2024"
    assert tariff.fiscal_year == 2024
    assert tariff.period == ISRPeriod.ANNUAL


def test_safe_selection_requires_effective_from(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "missing_effective_from.json",
        _verified_payload(
            fiscal_year=2026,
            period="annual",
            effective_from=None,
        ),
    )
    registry = load_isr_tariff_registry([path])

    with pytest.raises(ISRTariffRegistryError, match="fecha inicial de vigencia"):
        registry.select_for_fiscal_use(2026, ISRPeriod.ANNUAL)
