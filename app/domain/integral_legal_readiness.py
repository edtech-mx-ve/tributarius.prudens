from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class LegalCompletenessDimension(StrEnum):
    FACTS = "facts"
    NORMATIVE_BASIS = "normative_basis"
    RULE_REASONING = "rule_reasoning"
    CALCULATION = "calculation"


class LegalCompletenessState(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"
    NOT_APPLICABLE = "not_applicable"


class EvidentiarySufficiency(StrEnum):
    SUFFICIENT = "sufficient"
    LIMITED = "limited"
    INSUFFICIENT = "insufficient"


class LegalCompletenessItem(BaseModel):
    dimension: LegalCompletenessDimension
    state: LegalCompletenessState
    reason: str = Field(min_length=1, max_length=500)
    evidence_refs: list[str] = Field(default_factory=list, max_length=100)


class LegalAnalysisReadiness(BaseModel):
    """Completitud y suficiencia previas al cierre automático del análisis."""

    schema_version: str = "1.0"
    completeness: list[LegalCompletenessItem] = Field(min_length=1, max_length=10)
    missing_requirements: list[str] = Field(default_factory=list, max_length=50)
    evidentiary_sufficiency: EvidentiarySufficiency
    can_close_automatically: bool
    requires_clarification: bool = False
    requires_human_review: bool = False
