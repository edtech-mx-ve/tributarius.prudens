from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from app.domain.isr import ISRCalculationInput, ISRPeriod
from app.domain.normative import (
    NormativeValidityBasis,
    NormativeValidityScope,
    NormativeValidityStatus,
)
from calculators.isr import calculate_isr
from calculators.isr_tariff_registry import (
    load_isr_tariff,
    require_tariff_legal_metadata,
)

TARIFF_PATH = Path("calculators/tariffs/isr_annual_lisr_article_152_2024.json")


def test_controlled_lisr_article_152_tariff_loads_as_verified_source() -> None:
    tariff = load_isr_tariff(TARIFF_PATH)

    assert tariff.version == "LISR-ART152-CORPUS-2024"
    assert tariff.fiscal_year == 2024
    assert tariff.period == ISRPeriod.ANNUAL
    assert tariff.normative_ref == "lisr:articulo_152"
    assert tariff.verified is True
    assert len(tariff.brackets) == 11


def test_controlled_tariff_matches_article_152_boundary_rows() -> None:
    tariff = load_isr_tariff(TARIFF_PATH)

    first = tariff.brackets[0]
    middle = tariff.brackets[7]
    last = tariff.brackets[-1]

    assert (
        first.lower_limit,
        first.upper_limit,
        first.fixed_fee,
        first.rate_percent,
    ) == (
        Decimal("0.01"),
        Decimal("5952.84"),
        Decimal("0.00"),
        Decimal("1.92"),
    )
    assert (
        middle.lower_limit,
        middle.upper_limit,
        middle.fixed_fee,
        middle.rate_percent,
    ) == (
        Decimal("392841.97"),
        Decimal("750000.00"),
        Decimal("73703.41"),
        Decimal("30.00"),
    )
    assert (
        last.lower_limit,
        last.upper_limit,
        last.fixed_fee,
        last.rate_percent,
    ) == (
        Decimal("3000000.01"),
        None,
        Decimal("940850.81"),
        Decimal("35.00"),
    )


def test_real_tariff_has_traceable_legal_metadata() -> None:
    tariff = load_isr_tariff(TARIFF_PATH)
    metadata = require_tariff_legal_metadata(tariff)

    assert metadata.source_document_id == "lisr"
    assert metadata.legal_basis_refs == ["lisr:articulo_152"]
    assert metadata.validity_status == NormativeValidityStatus.UNKNOWN
    assert metadata.validity_scope == NormativeValidityScope.LEGAL_UNIT
    assert (
        metadata.validity_basis
        == NormativeValidityBasis.OFFICIAL_CONSOLIDATED_VERSION
    )
    assert metadata.official_source is not None
    assert "LISR.pdf" in metadata.official_source


def test_real_tariff_is_not_misrepresented_as_verified_2026_tariff() -> None:
    tariff = load_isr_tariff(TARIFF_PATH)
    metadata = require_tariff_legal_metadata(tariff)

    assert tariff.fiscal_year == 2024
    assert metadata.validity_status == NormativeValidityStatus.UNKNOWN
    assert metadata.effective_from is None
    assert metadata.effective_to is None


def test_real_tariff_drives_reproducible_article_152_calculation() -> None:
    tariff = load_isr_tariff(TARIFF_PATH)
    result = calculate_isr(
        ISRCalculationInput(
            fiscal_year=2024,
            period=ISRPeriod.ANNUAL,
            gross_income=Decimal("100000.00"),
            exempt_income=Decimal("0.00"),
            authorized_deductions=Decimal("0.00"),
            credits=Decimal("0.00"),
            normative_ref="lisr:articulo_152",
        ),
        tariff,
    )

    assert result.taxable_base == Decimal("100000.00")
    assert result.selected_lower_limit == Decimal("88793.05")
    assert result.selected_upper_limit == Decimal("103218.00")
    assert result.fixed_fee == Decimal("7130.48")
    assert result.rate_percent == Decimal("16.00")
    assert result.tax_before_credits == Decimal("8923.59")
    assert result.final_tax == Decimal("8923.59")
