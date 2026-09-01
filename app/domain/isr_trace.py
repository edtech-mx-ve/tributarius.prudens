from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from app.domain.isr import ISRCalculationStep, ISRPeriod
from app.domain.normative import NormativeValidityStatus


class ISRInputTrace(BaseModel):
    fiscal_year: int
    period: ISRPeriod
    gross_income: Decimal
    exempt_income: Decimal
    authorized_deductions: Decimal
    credits: Decimal
    normative_ref: str


class ISRBracketTrace(BaseModel):
    lower_limit: Decimal
    upper_limit: Decimal | None
    fixed_fee: Decimal
    rate_percent: Decimal


class ISRLegalTrace(BaseModel):
    normative_ref: str
    tariff_version: str
    source_reference: str
    source_document_id: str | None = None
    legal_basis_refs: list[str] = Field(default_factory=list)
    validity_status: NormativeValidityStatus = NormativeValidityStatus.UNKNOWN


class ISRRuleAuthorizationTrace(BaseModel):
    rule_id: str
    version: str
    conclusion_code: str
    normative_refs: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)


class ISRCalculationTrace(BaseModel):
    """Traza reconstruible del cálculo ISR y de su habilitación jurídica."""

    schema_version: str = Field(default="1.0", pattern=r"^1\.\d+$")
    input: ISRInputTrace
    bracket: ISRBracketTrace
    steps: list[ISRCalculationStep] = Field(min_length=1)
    legal: ISRLegalTrace
    authorization: ISRRuleAuthorizationTrace
    taxable_base: Decimal
    tax_before_credits: Decimal
    final_tax: Decimal


class ISRTraceVerification(BaseModel):
    mathematically_consistent: bool
    legally_linked: bool
    rbr_authorized: bool
    verified: bool
