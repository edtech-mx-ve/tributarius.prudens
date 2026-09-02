from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.legal_benchmark_evaluation import LegalBenchmarkEvaluation
from app.domain.legal_decision import LegalDecision


class LegalBenchmarkCaseRun(BaseModel):
    case_id: str = Field(min_length=1, max_length=100)
    retrieved_document_ids: list[str] = Field(default_factory=list, max_length=100)
    decision: LegalDecision
    evaluation: LegalBenchmarkEvaluation


class LegalBenchmarkRun(BaseModel):
    schema_version: str = "1.0"
    cases: list[LegalBenchmarkCaseRun] = Field(default_factory=list, max_length=500)
    passed_cases: int = Field(ge=0)
    total_cases: int = Field(ge=0)
    score: float = Field(ge=0.0, le=1.0)
    passed: bool
