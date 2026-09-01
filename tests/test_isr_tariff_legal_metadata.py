from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain.isr import (
    ISRBracket,
    ISRPeriod,
    ISRTariff,
    ISRTariffLegalMetadata,
)
from app.domain.normative import (
    NormativeValidityBasis,
    NormativeValidityScope,
    NormativeValidityStatus,
)
from calculators.isr_tariff_registry import (
    ISRTariffRegistryError,
    require_tariff_legal_metadata,
)


def _brackets() -> list[ISRBracket]:
    return [
        ISRBracket(
            lower_limit=Decimal("0.00"),
            upper_limit=None,
            fixed_fee=Decimal("0.00"),
            rate_percent=Decimal("10.00"),
        )
    ]


def _metadata() -> ISRTariffLegalMetadata:
    return ISRTariffLegalMetadata(
        source_document_id="lisr",
        legal_basis_refs=["lisr:articulo_152", "rmf_2026:anexo_8"],
        publication_date=date(2025, 12, 31),
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 12, 31),
        validity_status=NormativeValidityStatus.VERIFIED_IN_FORCE,
        validity_scope=NormativeValidityScope.FISCAL_YEAR,
        validity_basis=NormativeValidityBasis.FISCAL_YEAR_RULE,
        validity_verified_at=date(2026, 1, 1),
        official_source="Fuente normativa controlada de prueba.",
    )


def _tariff(
    *,
    legal_metadata: ISRTariffLegalMetadata | None,
    normative_ref: str = "lisr:articulo_152",
) -> ISRTariff:
    return ISRTariff(
        schema_version="1.0",
        version="2026.1",
        fiscal_year=2026,
        period=ISRPeriod.ANNUAL,
        normative_ref=normative_ref,
        source_reference="FIXTURE_ONLY_NOT_FOR_FISCAL_USE",
        verified=True,
        legal_metadata=legal_metadata,
        brackets=_brackets(),
    )


def test_legal_metadata_preserves_normative_provenance() -> None:
    metadata = _metadata()

    assert metadata.source_document_id == "lisr"
    assert metadata.legal_basis_refs == [
        "lisr:articulo_152",
        "rmf_2026:anexo_8",
    ]
    assert metadata.publication_date == date(2025, 12, 31)
    assert metadata.effective_from == date(2026, 1, 1)
    assert metadata.effective_to == date(2026, 12, 31)
    assert metadata.validity_status == NormativeValidityStatus.VERIFIED_IN_FORCE
    assert metadata.validity_scope == NormativeValidityScope.FISCAL_YEAR
    assert metadata.validity_basis == NormativeValidityBasis.FISCAL_YEAR_RULE
    assert metadata.validity_verified_at == date(2026, 1, 1)


def test_tariff_links_primary_normative_ref_to_legal_basis() -> None:
    tariff = _tariff(legal_metadata=_metadata())

    assert tariff.normative_ref in tariff.legal_metadata.legal_basis_refs  # type: ignore[union-attr]


def test_tariff_rejects_disconnected_primary_normative_ref() -> None:
    with pytest.raises(
        ValidationError,
        match="normative_ref debe estar incluido",
    ):
        _tariff(
            legal_metadata=_metadata(),
            normative_ref="lisr:articulo_999",
        )


def test_legal_metadata_rejects_inverted_effective_interval() -> None:
    with pytest.raises(
        ValidationError,
        match="effective_to no puede ser anterior",
    ):
        ISRTariffLegalMetadata(
            source_document_id="lisr",
            legal_basis_refs=["lisr:articulo_152"],
            effective_from=date(2026, 12, 31),
            effective_to=date(2026, 1, 1),
        )


def test_legal_metadata_rejects_duplicate_basis_refs() -> None:
    with pytest.raises(
        ValidationError,
        match="legal_basis_refs no puede contener referencias duplicadas",
    ):
        ISRTariffLegalMetadata(
            source_document_id="lisr",
            legal_basis_refs=["lisr:articulo_152", "lisr:articulo_152"],
        )


def test_fixture_compatibility_allows_tariff_without_legal_metadata() -> None:
    tariff = _tariff(legal_metadata=None)

    assert tariff.legal_metadata is None


def test_real_fiscal_use_requires_legal_metadata() -> None:
    tariff = _tariff(legal_metadata=None)

    with pytest.raises(
        ISRTariffRegistryError,
        match="no contiene metadatos jurídicos suficientes",
    ):
        require_tariff_legal_metadata(tariff)


def test_real_fiscal_use_returns_traceable_metadata() -> None:
    tariff = _tariff(legal_metadata=_metadata())

    metadata = require_tariff_legal_metadata(tariff)

    assert metadata.source_document_id == "lisr"
    assert metadata.official_source == "Fuente normativa controlada de prueba."
