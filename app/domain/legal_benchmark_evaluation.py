from __future__ import annotations

from pydantic import BaseModel, Field


class LegalBenchmarkCheck(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    passed: bool
    expected: str | None = Field(default=None, max_length=1000)
    observed: str | None = Field(default=None, max_length=1000)


class LegalBenchmarkEvaluation(BaseModel):
    schema_version: str = "1.0"
    case_id: str = Field(min_length=1, max_length=100)
    checks: list[LegalBenchmarkCheck] = Field(default_factory=list, max_length=50)
    passed_checks: int = Field(ge=0)
    total_checks: int = Field(ge=0)
    score: float = Field(ge=0.0, le=1.0)
    passed: bool
