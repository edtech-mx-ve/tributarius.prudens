from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.hybrid_integral_legal_analysis import HybridIntegralLegalAnalysis
from app.domain.hybrid_legal_decision import HybridLegalDecision
from app.domain.orchestration import HybridOrchestrationResult


class HybridLlamaRuntimeStatus(StrEnum):
    """Estado técnico F.10 del circuito Llama híbrido end-to-end."""

    COMPLETED = "completed"
    DEGRADED = "degraded"


class HybridLlamaRuntimeResult(BaseModel):
    """Resultado F.10: ejecución completa F.2-F.9 con proveedor estructurado."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    status: HybridLlamaRuntimeStatus
    provider_name: str = Field(min_length=1, max_length=100)
    model_name: str = Field(min_length=1, max_length=200)
    orchestration: HybridOrchestrationResult
    analysis: HybridIntegralLegalAnalysis
    decision: HybridLegalDecision
    h1_generation_attempted: bool
    h2_generation_attempted: bool
    semantic_verification_attempted: bool
    llm_failure_codes: list[str] = Field(default_factory=list, max_length=40)
    provider_is_test_double: bool = False
    production_requires_real_llama: bool = True
    mock_allowed_for_tests_only: bool = True
    single_decision_preserved: bool = True
    source_results_reexecuted: bool = False
    can_reassign_legal_authority: bool = False

    @model_validator(mode="after")
    def validate_runtime_result(self) -> HybridLlamaRuntimeResult:
        if len(self.llm_failure_codes) != len(set(self.llm_failure_codes)):
            raise ValueError("F.10 no admite códigos de fallo LLM duplicados.")
        if self.status is HybridLlamaRuntimeStatus.COMPLETED and self.llm_failure_codes:
            raise ValueError("F.10 COMPLETED no puede conservar fallos LLM pendientes.")
        if self.status is HybridLlamaRuntimeStatus.DEGRADED and not self.llm_failure_codes:
            raise ValueError("F.10 DEGRADED exige al menos un fallo LLM trazable.")
        return self
