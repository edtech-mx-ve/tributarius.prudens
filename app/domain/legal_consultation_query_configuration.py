from __future__ import annotations

import hashlib
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.explanation_mode import ExplanationMode


class LegalConsultationQueryConfiguration(BaseModel):
    """G.3: consulta y configuracion efectivamente usadas por la ejecucion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    query: str = Field(min_length=3, max_length=4000)
    query_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    query_date: date
    requested_fiscal_year: int | None = Field(
        default=None,
        ge=1900,
        le=2200,
    )
    resolved_fiscal_year: int | None = Field(
        default=None,
        ge=1900,
        le=2200,
    )
    explanation_mode: ExplanationMode
    top_k: int = Field(ge=1, le=20)
    session_jurisprudence_attached: bool = False

    source_request_already_validated: Literal[True] = True
    source_results_already_computed: Literal[True] = True
    can_change_legal_decision: Literal[False] = False

    @model_validator(mode="after")
    def validate_query_fingerprint(
        self,
    ) -> LegalConsultationQueryConfiguration:
        expected = hashlib.sha256(self.query.encode("utf-8")).hexdigest()
        if self.query_sha256 != expected:
            raise ValueError(
                "G.3 detecto una huella inconsistente para la consulta."
            )
        return self
