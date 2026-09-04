from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class HybridLlamaBenchmarkProviderKind(StrEnum):
    REFERENCE = "reference"
    REAL_LLAMA = "real_llama"


class HybridLlamaBenchmarkScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]{2,99}$")
    description: str = Field(min_length=1, max_length=500)
    with_jurisprudence: bool = False
    expect_h2: bool = False
    expect_human_review: bool = False
    expected_conclusion: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_scenario(self) -> HybridLlamaBenchmarkScenario:
        if self.expect_h2 and not self.with_jurisprudence:
            raise ValueError("F.12 no puede exigir H2 sin jurisprudencia de sesión.")
        return self


class HybridLlamaBenchmarkThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generation_success: float = Field(default=1.0, ge=0.0, le=1.0)
    hypothesis_quality: float = Field(default=1.0, ge=0.0, le=1.0)
    normative_grounding: float = Field(default=1.0, ge=0.0, le=1.0)
    ratio_fidelity: float = Field(default=1.0, ge=0.0, le=1.0)
    obiter_separation: float = Field(default=1.0, ge=0.0, le=1.0)
    rbs_consistency: float = Field(default=1.0, ge=0.0, le=1.0)
    cbr_consistency: float = Field(default=1.0, ge=0.0, le=1.0)
    jurisprudence_compliance: float = Field(default=1.0, ge=0.0, le=1.0)
    argument_consistency: float = Field(default=1.0, ge=0.0, le=1.0)
    human_review_precision: float = Field(default=1.0, ge=0.0, le=1.0)
    legal_authority_integrity: float = Field(default=1.0, ge=0.0, le=1.0)
    single_decision_integrity: float = Field(default=1.0, ge=0.0, le=1.0)
    conclusion_stability: float = Field(default=1.0, ge=0.0, le=1.0)
    hallucination_rate_max: float = Field(default=0.0, ge=0.0, le=1.0)


class HybridLlamaBenchmarkSuite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    suite_id: str = Field(min_length=1, max_length=120)
    scenarios: list[HybridLlamaBenchmarkScenario] = Field(min_length=2, max_length=20)
    thresholds: HybridLlamaBenchmarkThresholds = Field(
        default_factory=HybridLlamaBenchmarkThresholds
    )

    @model_validator(mode="after")
    def validate_unique_scenarios(self) -> HybridLlamaBenchmarkSuite:
        ids = [item.scenario_id for item in self.scenarios]
        if len(ids) != len(set(ids)):
            raise ValueError("F.12 no admite escenarios duplicados.")
        if not any(item.with_jurisprudence for item in self.scenarios):
            raise ValueError("F.12 exige al menos un escenario con jurisprudencia.")
        if not any(not item.with_jurisprudence for item in self.scenarios):
            raise ValueError("F.12 exige al menos un escenario sin jurisprudencia.")
        return self


class HybridLlamaBenchmarkCaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    provider_kind: HybridLlamaBenchmarkProviderKind
    provider_name: str = Field(min_length=1, max_length=100)
    model_name: str = Field(min_length=1, max_length=200)
    provider_is_test_double: bool
    runtime_completed: bool
    decision_status: str
    conclusion: str | None = Field(default=None, max_length=4000)
    requires_human_review: bool
    h1_generated: bool
    h2_expected: bool
    h2_generated: bool
    semantic_verification_performed: bool
    llm_failure_codes: list[str] = Field(default_factory=list, max_length=40)
    metrics: dict[str, float]
    failures: list[str] = Field(default_factory=list, max_length=80)
    passed: bool
    duration_seconds: float = Field(ge=0.0)


class HybridLlamaBenchmarkProviderReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_kind: HybridLlamaBenchmarkProviderKind
    provider_name: str
    model_name: str
    case_count: int = Field(ge=1)
    passed_case_count: int = Field(ge=0)
    aggregate_metrics: dict[str, float]
    overall_passed: bool
    cases: list[HybridLlamaBenchmarkCaseResult]


class HybridLlamaBenchmarkComparisonCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    same_decision_status: bool
    same_conclusion: bool
    conclusion_stability: float = Field(ge=0.0, le=1.0)
    reference_requires_human_review: bool
    real_requires_human_review: bool


class HybridLlamaBenchmarkReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    suite_id: str
    suite_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    reference: HybridLlamaBenchmarkProviderReport
    real_llama: HybridLlamaBenchmarkProviderReport
    comparison_cases: list[HybridLlamaBenchmarkComparisonCase]
    conclusion_stability: float = Field(ge=0.0, le=1.0)
    hallucination_rate: float = Field(ge=0.0, le=1.0)
    safety_passed: bool
    quality_passed: bool
    overall_passed: bool
    real_provider_required: bool = True
    mock_allowed_for_reference_only: bool = True
    limitations: list[str] = Field(default_factory=list, max_length=20)
