from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class LegalConsequenceKind(StrEnum):
    """Clase de efecto derivado de la determinación jurídica existente."""

    OBLIGATION = "obligation"
    RIGHT = "right"
    ACTION = "action"
    RISK = "risk"
    DEADLINE = "deadline"


class LegalConsequenceStatus(StrEnum):
    """Grado de determinación del efecto jurídico."""

    DETERMINED = "determined"
    CONDITIONAL = "conditional"
    UNRESOLVED = "unresolved"


class LegalConsequence(BaseModel):
    """Consecuencia jurídica respaldada por referencias ya existentes."""

    kind: LegalConsequenceKind
    status: LegalConsequenceStatus
    description: str = Field(min_length=1, max_length=2000)
    normative_refs: list[str] = Field(default_factory=list, max_length=100)
    evidence_refs: list[str] = Field(default_factory=list, max_length=200)
    source_rule_refs: list[str] = Field(default_factory=list, max_length=100)
    requires_human_review: bool = False


class LegalConsequences(BaseModel):
    """Colección estructurada de efectos jurídicos sin inferencias nuevas."""

    schema_version: str = "1.0"
    items: list[LegalConsequence] = Field(default_factory=list, max_length=200)
