from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.query import FactOrigin


class LegalFactStatus(StrEnum):
    """Estado probatorio de un hecho dentro de Legal Decision 1.0."""

    SUPPLIED = "supplied"
    INFERRED = "inferred"
    ACCREDITED = "accredited"
    CONTESTED = "contested"
    MISSING = "missing"


class LegalFactMateriality(StrEnum):
    """Relevancia del hecho para la determinación jurídica."""

    MATERIAL = "material"
    CONTEXTUAL = "contextual"
    UNDETERMINED = "undetermined"


class LegalFactAssessment(BaseModel):
    """Valoración estructurada sin convertir afirmaciones en hechos probados."""

    name: str = Field(min_length=1, max_length=100)
    value: str | None = Field(default=None, max_length=1000)
    origin: FactOrigin | None = None
    status: LegalFactStatus
    materiality: LegalFactMateriality
    basis: str = Field(min_length=1, max_length=500)
    evidence_refs: list[str] = Field(default_factory=list, max_length=100)
    requires_clarification: bool = False
