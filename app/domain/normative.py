from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class NormativeDecision(StrEnum):
    APPLICABLE = "applicable"
    NOT_YET_EFFECTIVE = "not_yet_effective"
    EXPIRED = "expired"
    FISCAL_YEAR_MISMATCH = "fiscal_year_mismatch"
    UNKNOWN_VALIDITY = "unknown_validity"
    INVALID_DATA = "invalid_data"


class NormativeValidityStatus(StrEnum):
    VERIFIED_IN_FORCE = "verified_in_force"
    VERIFIED_FUTURE = "verified_future"
    VERIFIED_EXPIRED = "verified_expired"
    UNKNOWN = "unknown"
    CONFLICTING = "conflicting"


class NormativeValidityScope(StrEnum):
    DOCUMENT = "document"
    LEGAL_UNIT = "legal_unit"
    AMENDMENT = "amendment"
    FISCAL_YEAR = "fiscal_year"
    UNKNOWN = "unknown"


class NormativeValidityBasis(StrEnum):
    EXPLICIT_EFFECTIVE_DATE = "explicit_effective_date"
    OFFICIAL_CONSOLIDATED_VERSION = "official_consolidated_version"
    VERIFIED_REFORM_CHAIN = "verified_reform_chain"
    FISCAL_YEAR_RULE = "fiscal_year_rule"
    UNKNOWN = "unknown"


class NormativeApplicabilityRequest(BaseModel):
    legal_unit_id: int = Field(gt=0)
    version_label: str = Field(min_length=1, max_length=200)
    effective_from: date | None = None
    effective_to: date | None = None
    fiscal_year: int | None = Field(default=None, ge=1900, le=2200)
    validity_status: NormativeValidityStatus = NormativeValidityStatus.UNKNOWN
    validity_scope: NormativeValidityScope = NormativeValidityScope.UNKNOWN
    validity_basis: NormativeValidityBasis = NormativeValidityBasis.UNKNOWN
    validity_verified_at: date | None = None
    official_source: str | None = Field(default=None, max_length=1000)
    query_date: date
    query_fiscal_year: int | None = Field(default=None, ge=1900, le=2200)

    @model_validator(mode="after")
    def validate_interval(self) -> NormativeApplicabilityRequest:
        if (
            self.effective_from is not None
            and self.effective_to is not None
            and self.effective_to < self.effective_from
        ):
            raise ValueError("effective_to no puede ser anterior a effective_from.")
        return self


class NormativeApplicabilityResult(BaseModel):
    legal_unit_id: int
    version_label: str
    decision: NormativeDecision
    applicable: bool
    evidence_available: bool = True
    query_date: date
    query_fiscal_year: int | None
    effective_from: date | None
    effective_to: date | None
    fiscal_year: int | None
    validity_status: NormativeValidityStatus = NormativeValidityStatus.UNKNOWN
    validity_scope: NormativeValidityScope = NormativeValidityScope.UNKNOWN
    validity_basis: NormativeValidityBasis = NormativeValidityBasis.UNKNOWN
    validity_verified_at: date | None = None
    official_source: str | None = None
    reason: str = Field(min_length=1, max_length=1000)
    requires_human_review: bool = False


class NormativeSelectionRequest(BaseModel):
    legal_unit_id: int = Field(gt=0)
    query_date: date
    query_fiscal_year: int | None = Field(default=None, ge=1900, le=2200)


class NormativeVersionView(BaseModel):
    version_label: str
    effective_from: date | None = None
    effective_to: date | None = None
    fiscal_year: int | None = Field(default=None, ge=1900, le=2200)
    publication_date: date | None = None
    validity_status: NormativeValidityStatus = NormativeValidityStatus.UNKNOWN
    validity_scope: NormativeValidityScope = NormativeValidityScope.UNKNOWN
    validity_basis: NormativeValidityBasis = NormativeValidityBasis.UNKNOWN
    validity_verified_at: date | None = None
    official_source: str | None = None
    source_reference: str | None = None
