from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class LegalBenchmarkAcceptanceStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NO_EVIDENCE = "no_evidence"


class LegalBenchmarkQualityReport(BaseModel):
    schema_version: str = "1.0"
    dataset_case_count: int = Field(ge=0)
    executed_case_count: int = Field(ge=0)
    passed_case_count: int = Field(ge=0)
    failed_case_count: int = Field(ge=0)
    case_pass_rate: float = Field(ge=0.0, le=1.0)
    total_checks: int = Field(ge=0)
    passed_checks: int = Field(ge=0)
    failed_checks: int = Field(ge=0)
    check_pass_rate: float = Field(ge=0.0, le=1.0)
    human_review_expected_cases: int = Field(ge=0)
    human_review_correct_cases: int = Field(ge=0)
    human_review_pass_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    llm_controller_violations: int = Field(ge=0)
    integrity_complete: bool
    dataset_coverage_complete: bool
    acceptance_status: LegalBenchmarkAcceptanceStatus
    acceptance_reasons: list[str] = Field(default_factory=list, max_length=50)
    known_limitations: list[str] = Field(default_factory=list, max_length=50)
