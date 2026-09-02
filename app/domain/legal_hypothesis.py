from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class LegalHypothesisStatus(StrEnum):
    """Estado de una hipótesis generativa antes de validación jurídica."""

    PROPOSED = "proposed"
    REJECTED = "rejected"


class ControlledLegalHypothesis(BaseModel):
    """Hipótesis jurídica orientativa que carece de autoridad decisoria."""

    issue: str = Field(min_length=1, max_length=1000)
    hypothesis: str = Field(min_length=1, max_length=4000)
    investigation_targets: list[str] = Field(default_factory=list, max_length=20)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    uncertainties: list[str] = Field(default_factory=list, max_length=20)
    status: LegalHypothesisStatus = LegalHypothesisStatus.PROPOSED
    requires_validation: bool = True
    changes_deterministic_result: bool = False
    asserts_external_legal_authority: bool = False


class ControlledLegalHypothesisResult(BaseModel):
    """Resultado trazable del experimento de hipótesis jurídica controlada."""

    generation_performed: bool
    hypothesis: ControlledLegalHypothesis | None = None
    authorized_evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    requires_human_review: bool = False
    trace: list[str] = Field(default_factory=list, max_length=20)
