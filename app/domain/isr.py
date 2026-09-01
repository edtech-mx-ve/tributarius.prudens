from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from app.domain.normative import (
    NormativeValidityBasis,
    NormativeValidityScope,
    NormativeValidityStatus,
)


class ISRPeriod(StrEnum):
    MONTHLY = "monthly"
    ANNUAL = "annual"


class ISRBracket(BaseModel):
    lower_limit: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    upper_limit: Decimal | None = Field(
        default=None, ge=0, max_digits=18, decimal_places=2
    )
    fixed_fee: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    rate_percent: Decimal = Field(ge=0, le=100, max_digits=7, decimal_places=4)


class ISRTariffLegalMetadata(BaseModel):
    """Metadatos jurídicos trazables asociados a una tarifa ISR."""

    source_document_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    legal_basis_refs: list[str] = Field(min_length=1, max_length=20)
    publication_date: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    validity_status: NormativeValidityStatus = NormativeValidityStatus.UNKNOWN
    validity_scope: NormativeValidityScope = NormativeValidityScope.FISCAL_YEAR
    validity_basis: NormativeValidityBasis = NormativeValidityBasis.FISCAL_YEAR_RULE
    validity_verified_at: date | None = None
    official_source: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_interval(self) -> ISRTariffLegalMetadata:
        if (
            self.effective_from is not None
            and self.effective_to is not None
            and self.effective_to < self.effective_from
        ):
            raise ValueError("effective_to no puede ser anterior a effective_from.")
        if len(set(self.legal_basis_refs)) != len(self.legal_basis_refs):
            raise ValueError("legal_basis_refs no puede contener referencias duplicadas.")
        return self


class ISRTariff(BaseModel):
    schema_version: str = Field(pattern=r"^1\.\d+$")
    version: str = Field(min_length=1, max_length=50)
    fiscal_year: int = Field(ge=1900, le=2200)
    period: ISRPeriod
    normative_ref: str = Field(min_length=1, max_length=300)
    source_reference: str = Field(min_length=1, max_length=1000)
    verified: bool
    legal_metadata: ISRTariffLegalMetadata | None = None
    brackets: list[ISRBracket] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def require_verified_source(self) -> ISRTariff:
        if not self.verified:
            raise ValueError("La tarifa debe estar marcada como verificada.")
        return self

    @model_validator(mode="after")
    def validate_legal_metadata_link(self) -> ISRTariff:
        if (
            self.legal_metadata is not None
            and self.normative_ref not in self.legal_metadata.legal_basis_refs
        ):
            raise ValueError(
                "normative_ref debe estar incluido en legal_metadata.legal_basis_refs."
            )
        return self


class ISRCalculationInput(BaseModel):
    fiscal_year: int = Field(ge=1900, le=2200)
    period: ISRPeriod
    gross_income: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    exempt_income: Decimal = Field(default=Decimal("0"), ge=0)
    authorized_deductions: Decimal = Field(default=Decimal("0"), ge=0)
    credits: Decimal = Field(default=Decimal("0"), ge=0)
    normative_ref: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def validate_components(self) -> ISRCalculationInput:
        if self.exempt_income > self.gross_income:
            raise ValueError("El ingreso exento no puede superar el ingreso bruto.")
        return self


class ISRCalculationStep(BaseModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    formula: str
    result: Decimal


class ISRCalculationResult(BaseModel):
    fiscal_year: int
    period: ISRPeriod
    taxable_base: Decimal
    selected_lower_limit: Decimal
    selected_upper_limit: Decimal | None
    fixed_fee: Decimal
    rate_percent: Decimal
    tax_before_credits: Decimal
    credits: Decimal
    final_tax: Decimal
    normative_ref: str
    tariff_version: str
    source_reference: str
    steps: list[ISRCalculationStep]
