from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class LegalHypothesisVerificationState(StrEnum):
    """Estado del contraste entre hipótesis generativa y resultado determinista."""

    NOT_APPLICABLE = "not_applicable"
    COMPARED = "compared"
    INCONCLUSIVE = "inconclusive"


class LegalHypothesisVerificationResult(BaseModel):
    """Contraste conservador que no convierte similitud textual en validez jurídica."""

    state: LegalHypothesisVerificationState
    hypothesis_text: str | None = Field(default=None, max_length=4000)
    deterministic_conclusions: list[str] = Field(default_factory=list, max_length=100)
    controlling_source: str | None = Field(default=None, max_length=100)
    authorized_evidence_preserved: bool = True
    exact_text_match: bool | None = None
    semantic_equivalence_asserted: bool = False
    deterministic_result_preserved: bool = True
    findings: list[str] = Field(default_factory=list, max_length=20)
    trace: list[str] = Field(default_factory=list, max_length=20)
