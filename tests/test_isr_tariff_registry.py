from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.domain.isr import ISRPeriod
from calculators.isr_tariff_registry import (
    ISRTariffRegistry,
    ISRTariffRegistryError,
    load_isr_tariff,
    load_isr_tariff_registry,
)


def _payload(
    *,
    fiscal_year: int,
    period: str = "annual",
    month: int | None = None,
    version: str = "TEST-1.0",
    normative_ref: str = "NORM_TEST_ISR",
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "version": version,
        "fiscal_year": fiscal_year,
        "period": period,
        "month": (
            month
            if month is not None
            else (1 if period == "monthly" else None)
        ),
        "tariff_scope": (
            "year_to_month"
            if period == "monthly"
            else "annual"
        ),
        "normative_ref": normative_ref,
        "source_reference": "FIXTURE_ONLY_NOT_FOR_FISCAL_USE",
        "verified": True,
        "brackets": [
            {
                "lower_limit": "0.00",
                "upper_limit": "10000.00",
                "fixed_fee": "0.00",
                "rate_percent": "10.0000",
            },
            {
                "lower_limit": "10000.01",
                "upper_limit": None,
                "fixed_fee": "1000.00",
                "rate_percent": "20.0000",
            },
        ],
    }


def _write(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_tariff_preserves_version_and_legal_provenance(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "isr_2026.json",
        _payload(
            fiscal_year=2026,
            version="2026.1",
            normative_ref="lisr:articulo_152",
        ),
    )

    tariff = load_isr_tariff(path)

    assert tariff.fiscal_year == 2026
    assert tariff.version == "2026.1"
    assert tariff.normative_ref == "lisr:articulo_152"
    assert tariff.source_reference == "FIXTURE_ONLY_NOT_FOR_FISCAL_USE"
    assert tariff.verified is True


def test_registry_selects_exact_fiscal_year_and_period(tmp_path: Path) -> None:
    annual_2025 = _write(
        tmp_path / "isr_2025.json",
        _payload(fiscal_year=2025, version="2025.1"),
    )
    annual_2026 = _write(
        tmp_path / "isr_2026.json",
        _payload(fiscal_year=2026, version="2026.1"),
    )

    registry = load_isr_tariff_registry([annual_2025, annual_2026])

    assert registry.get(2025, ISRPeriod.ANNUAL).version == "2025.1"
    assert registry.get(2026, ISRPeriod.ANNUAL).version == "2026.1"


def test_registry_fails_closed_when_year_is_missing(tmp_path: Path) -> None:
    path = _write(tmp_path / "isr_2026.json", _payload(fiscal_year=2026))
    registry = load_isr_tariff_registry([path])

    with pytest.raises(
        ISRTariffRegistryError,
        match="No existe una tarifa ISR verificada",
    ):
        registry.get(2025, ISRPeriod.ANNUAL)


def test_registry_never_substitutes_monthly_for_annual(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "isr_monthly_2026.json",
        _payload(fiscal_year=2026, period="monthly"),
    )
    registry = load_isr_tariff_registry([path])

    with pytest.raises(
        ISRTariffRegistryError,
        match="No existe una tarifa ISR verificada",
    ):
        registry.get(2026, ISRPeriod.ANNUAL)


def test_registry_rejects_duplicate_year_and_period(tmp_path: Path) -> None:
    first = _write(
        tmp_path / "first.json",
        _payload(fiscal_year=2026, version="2026.1"),
    )
    second = _write(
        tmp_path / "second.json",
        _payload(fiscal_year=2026, version="2026.2"),
    )

    with pytest.raises(
        ISRTariffRegistryError,
        match="más de una tarifa ISR",
    ):
        load_isr_tariff_registry([first, second])


def test_loader_rejects_unverified_tariff(tmp_path: Path) -> None:
    payload = _payload(fiscal_year=2026)
    payload["verified"] = False
    path = _write(tmp_path / "unverified.json", payload)

    with pytest.raises(ISRTariffRegistryError, match="tarifa ISR válida"):
        load_isr_tariff(path)


def test_loader_rejects_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ISRTariffRegistryError, match="tarifa ISR válida"):
        load_isr_tariff(path)


def test_registry_exposes_stable_audit_order(tmp_path: Path) -> None:
    annual_2026 = load_isr_tariff(
        _write(tmp_path / "annual.json", _payload(fiscal_year=2026))
    )
    monthly_2026 = load_isr_tariff(
        _write(
            tmp_path / "monthly.json",
            _payload(fiscal_year=2026, period="monthly", version="M-2026"),
        )
    )
    annual_2025 = load_isr_tariff(
        _write(tmp_path / "old.json", _payload(fiscal_year=2025, version="A-2025"))
    )

    registry = ISRTariffRegistry([annual_2026, monthly_2026, annual_2025])

    assert [
        (tariff.fiscal_year, tariff.period.value, tariff.version)
        for tariff in registry.tariffs
    ] == [
        (2025, "annual", "A-2025"),
        (2026, "annual", "TEST-1.0"),
        (2026, "monthly", "M-2026"),
    ]

def test_registry_selects_exact_monthly_tariff(
    tmp_path: Path,
) -> None:
    january = _write(
        tmp_path / "january.json",
        _payload(
            fiscal_year=2026,
            period="monthly",
            month=1,
            version="M-2026-01",
            normative_ref="lisr:articulo_106",
        ),
    )
    september = _write(
        tmp_path / "september.json",
        _payload(
            fiscal_year=2026,
            period="monthly",
            month=9,
            version="M-2026-09",
            normative_ref="lisr:articulo_106",
        ),
    )

    registry = load_isr_tariff_registry(
        [january, september]
    )

    assert (
        registry.get(
            2026,
            ISRPeriod.MONTHLY,
            1,
        ).version
        == "M-2026-01"
    )
    assert (
        registry.get(
            2026,
            ISRPeriod.MONTHLY,
            9,
        ).version
        == "M-2026-09"
    )

    with pytest.raises(
        ISRTariffRegistryError,
        match="No existe una tarifa ISR verificada",
    ):
        registry.get(
            2026,
            ISRPeriod.MONTHLY,
            8,
        )


def test_loader_rejects_monthly_tariff_without_month(
    tmp_path: Path,
) -> None:
    payload = _payload(
        fiscal_year=2026,
        period="monthly",
        normative_ref="lisr:articulo_106",
    )
    payload["month"] = None

    path = _write(
        tmp_path / "monthly_without_month.json",
        payload,
    )

    with pytest.raises(
        ISRTariffRegistryError,
        match="tarifa ISR",
    ):
        load_isr_tariff(path)


def test_loader_rejects_monthly_tariff_with_annual_scope(
    tmp_path: Path,
) -> None:
    payload = _payload(
        fiscal_year=2026,
        period="monthly",
        month=9,
        normative_ref="lisr:articulo_106",
    )
    payload["tariff_scope"] = "annual"

    path = _write(
        tmp_path / "monthly_wrong_scope.json",
        payload,
    )

    with pytest.raises(
        ISRTariffRegistryError,
        match="tarifa ISR",
    ):
        load_isr_tariff(path)
