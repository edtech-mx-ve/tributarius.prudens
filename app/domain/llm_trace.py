from __future__ import annotations

from pydantic import BaseModel, Field

from llm.models import ExplanationMode


class LLMTrace(BaseModel):
    provider_name: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    explanation_mode: ExplanationMode
    evidence_ids: list[str] = Field(default_factory=list)
    normative_refs: list[str] = Field(default_factory=list)
    rule_refs: list[str] = Field(default_factory=list)
    calculation_refs: list[str] = Field(default_factory=list)
    cbr_refs: list[str] = Field(default_factory=list)
    jurisprudence_refs: list[str] = Field(default_factory=list)
    generated: bool
    requires_human_review: bool
    uncertainties: list[str] = Field(default_factory=list)
