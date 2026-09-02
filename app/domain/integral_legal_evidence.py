from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class IntegralLegalEvidenceChannel(StrEnum):
    NORMATIVE = "normative"
    RBS = "rbs"
    CBR = "cbr"
    JURISPRUDENCE = "jurisprudence"
    CALCULATION = "calculation"


class IntegralLegalEvidenceItem(BaseModel):
    channel: IntegralLegalEvidenceChannel
    present: bool
    references: list[str] = Field(default_factory=list, max_length=200)
    requires_human_review: bool = False


class IntegralLegalEvidenceMap(BaseModel):
    """Mapa de fuentes jurídicas ya producidas por la orquestación."""

    schema_version: str = "1.0"
    items: list[IntegralLegalEvidenceItem] = Field(min_length=5, max_length=5)
