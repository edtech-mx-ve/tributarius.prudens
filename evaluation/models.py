from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvaluationCaseKind(StrEnum):
    NORMAL = "normal"
    ABSTENTION = "abstention"
    ADVERSARIAL = "adversarial"


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]{2,99}$")
    kind: EvaluationCaseKind = EvaluationCaseKind.NORMAL
    expected_intent: str | None = Field(default=None, max_length=100)
    expected_relevant_chunk_ids: list[str] = Field(default_factory=list, max_length=50)
    expected_applicable_normative_refs: list[str] = Field(
        default_factory=list,
        max_length=50,
    )
    expected_rule_ids: list[str] = Field(default_factory=list, max_length=50)
    expected_calculations: dict[str, str] = Field(default_factory=dict)
    expected_evidence_ids: list[str] = Field(default_factory=list, max_length=50)
    expect_human_review: bool = False
    expect_abstention: bool = False
    tags: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_case_semantics(self) -> EvaluationCase:
        if self.kind == EvaluationCaseKind.ABSTENTION and not self.expect_abstention:
            raise ValueError("Los casos abstention deben exigir abstención.")
        return self


class MetricResult(BaseModel):
    name: str
    value: float = Field(ge=0.0, le=1.0)
    passed: bool
    threshold: float = Field(ge=0.0, le=1.0)


class CaseEvaluationResult(BaseModel):
    case_id: str
    passed: bool
    metrics: dict[str, float]
    failures: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class EvaluationThresholds(BaseModel):
    intent_accuracy: float = Field(default=0.90, ge=0.0, le=1.0)
    retrieval_recall_at_k: float = Field(default=0.80, ge=0.0, le=1.0)
    citation_precision: float = Field(default=0.95, ge=0.0, le=1.0)
    citation_recall: float = Field(default=0.80, ge=0.0, le=1.0)
    normative_accuracy: float = Field(default=0.95, ge=0.0, le=1.0)
    rule_accuracy: float = Field(default=0.95, ge=0.0, le=1.0)
    calculation_accuracy: float = Field(default=1.00, ge=0.0, le=1.0)
    review_accuracy: float = Field(default=0.95, ge=0.0, le=1.0)
    abstention_accuracy: float = Field(default=0.95, ge=0.0, le=1.0)
    trace_consistency: float = Field(default=1.00, ge=0.0, le=1.0)


class IntegralEvaluationReport(BaseModel):
    schema_version: str = "1.0"
    dataset_id: str = Field(min_length=1, max_length=200)
    dataset_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    case_count: int = Field(ge=1)
    passed_case_count: int = Field(ge=0)
    overall_passed: bool
    metrics: list[MetricResult]
    cases: list[CaseEvaluationResult]
    limitations: list[str] = Field(default_factory=list)
