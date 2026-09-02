from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class LegalReasoningStepKind(StrEnum):
    """Tipo de paso dentro de la cadena jurídica estructurada."""

    RULE_APPLICATION = "rule_application"
    FINAL_DETERMINATION = "final_determination"


class LegalReasoningStep(BaseModel):
    """Paso trazable que solo referencia elementos ya presentes en Legal Decision."""

    sequence: int = Field(ge=1)
    kind: LegalReasoningStepKind
    fact_refs: list[str] = Field(default_factory=list, max_length=100)
    normative_refs: list[str] = Field(default_factory=list, max_length=100)
    rule_ref: str | None = Field(default=None, max_length=200)
    evidence_refs: list[str] = Field(default_factory=list, max_length=200)
    inference_code: str | None = Field(default=None, max_length=100)
    conclusion: str | None = Field(default=None, max_length=4000)
    controlling_source: str | None = Field(default=None, max_length=100)
    requires_human_review: bool = False


class LegalReasoningChain(BaseModel):
    """Cadena jurídica determinista; no genera normas ni inferencias nuevas."""

    schema_version: str = "1.0"
    steps: list[LegalReasoningStep] = Field(default_factory=list, max_length=200)
