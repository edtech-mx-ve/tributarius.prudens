from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class LegalHeuristicKind(StrEnum):
    """Familias de heurísticas jurídicas explícitas y auditables."""

    EVIDENCE_SUFFICIENCY = "evidence_sufficiency"
    NORMATIVE_RELEVANCE = "normative_relevance"
    TEMPORAL_CONFLICT = "temporal_conflict"
    HUMAN_REVIEW = "human_review"
    ANALYSIS_PRIORITY = "analysis_priority"


class LegalHeuristicLevel(StrEnum):
    """Severidad operativa de una señal heurística."""

    INFO = "info"
    WARNING = "warning"
    REVIEW = "review"


class LegalHeuristicSignal(BaseModel):
    """Señal heurística explicable que no sustituye una conclusión jurídica."""

    code: str
    kind: LegalHeuristicKind
    level: LegalHeuristicLevel
    message: str
    evidence_refs: list[str] = Field(default_factory=list)
    requires_review: bool = False


class LegalHeuristicEvaluation(BaseModel):
    """Resultado agregado de heurísticas sobre una decisión híbrida ya formada."""

    canonical_conclusion: str | None = None
    controlling_source: str | None = None
    signals: list[LegalHeuristicSignal] = Field(default_factory=list)
    analysis_priority: list[str] = Field(default_factory=list)
    requires_review: bool = False
    normative_priority_preserved: bool = True
    trace: list[str] = Field(default_factory=list)
