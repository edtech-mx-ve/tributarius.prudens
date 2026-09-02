from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class GoldenCaseCategory(StrEnum):
    NORMATIVE = "normative"
    OBLIGATION = "obligation"
    RIGHT = "right"
    CALCULATION = "calculation"
    AUTHORITY_ACT = "authority_act"
    DEFENSE = "defense"
    TEMPORAL = "temporal"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    ADVERSARIAL = "adversarial"


class GoldenCaseExpectation(BaseModel):
    primary_document_ids: list[str] = Field(default_factory=list, max_length=20)
    supporting_document_ids: list[str] = Field(default_factory=list, max_length=20)
    allowed_controlling_sources: list[str] = Field(default_factory=list, max_length=10)
    requires_human_review: bool | None = None
    conclusion_required: bool | None = None


class GoldenLegalCase(BaseModel):
    case_id: str = Field(min_length=1, max_length=100)
    category: GoldenCaseCategory
    query: str = Field(min_length=1, max_length=4000)
    fiscal_year: int | None = Field(default=None, ge=2000, le=2100)
    expectation: GoldenCaseExpectation
    source_case_id: str | None = Field(default=None, max_length=100)
    validation_notes: str = Field(min_length=1, max_length=1000)
