from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ReasoningSource(StrEnum):
    """Origen del conocimiento normalizado para coordinación híbrida."""

    RBS = "rbs"
    CBR = "cbr"


class NormalizedReasoningResult(BaseModel):
    """Contrato neutral entre RBS y CBR.

    No concede la misma autoridad jurídica a ambos motores. Únicamente hace
    comparables sus salidas para que un coordinador posterior pueda
    contrastarlas sin reescribir los motores existentes.
    """

    reasoning_source: ReasoningSource
    conclusion: str | None = None
    legal_basis: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    uncertainty: list[str] = Field(default_factory=list)
    applicability: bool | None = None
    temporal_context: str | None = None
    supporting_facts: list[str] = Field(default_factory=list)
    conflicting_facts: list[str] = Field(default_factory=list)
    requires_review: bool = False
    trace: list[str] = Field(default_factory=list)
