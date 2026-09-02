from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.hybrid_reasoning import NormalizedReasoningResult


class HybridReasoningRelation(StrEnum):
    """Relación entre conocimiento explícito RBS y experiencia CBR."""

    CONFIRMATION = "confirmation"
    CORRECTION = "correction"
    CONTRADICTION = "contradiction"
    EXCEPTION = "exception"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    HUMAN_REVIEW = "human_review"


class HybridCoordinationContext(BaseModel):
    """Señales jurídicas explícitas que el coordinador no debe inventar."""

    exception_supported: bool = False
    exception_basis: list[str] = Field(default_factory=list)


class HybridCoordinationFactors(BaseModel):
    """Factores verificables usados para justificar la decisión híbrida."""

    rbs_has_conclusion: bool
    rbs_applicability: bool | None = None
    cbr_applicability: bool | None = None
    cbr_similarity: float | None = Field(default=None, ge=0.0, le=1.0)
    cbr_temporal_context: str | None = None
    shared_legal_basis_count: int = Field(ge=0)
    rbs_requires_review: bool = False
    cbr_requires_review: bool = False
    normative_priority_preserved: bool = True


class HybridCoordinationResult(BaseModel):
    """Conclusión canónica y trazable del contraste RBS-CBR."""

    relation: HybridReasoningRelation
    conclusion: str | None = None
    controlling_source: str | None = None
    rbs_result: NormalizedReasoningResult
    cbr_result: NormalizedReasoningResult
    factors: HybridCoordinationFactors
    shared_legal_basis: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    requires_review: bool = False
    trace: list[str] = Field(default_factory=list)
