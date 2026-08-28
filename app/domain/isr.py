from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


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


class ISRTariff(BaseModel):
    schema_version: str = Field(pattern=r"^1\.\d+$")
    version: str = Field(min_length=1, max_length=50)
    fiscal_year: int = Field(ge=1900, le=2200)
    period: ISRPeriod
    normative_ref: str = Field(min_length=1, max_length=300)
    source_reference: str = Field(min_length=1, max_length=1000)
    verified: bool
    brackets: list[ISRBracket] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def require_verified_source(self) -> ISRTariff:
        if not self.verified:
            raise ValueError("La tarifa debe estar marcada como verificada.")
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
