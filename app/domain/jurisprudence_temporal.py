from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.jurisprudence import JurisprudenceCriterionType, JurisprudenceStatus


class JurisprudencePublicationDatePrecision(StrEnum):
    DAY = "day"
    MONTH = "month"
    YEAR = "year"
    UNKNOWN = "unknown"
    INVALID = "invalid"


class JurisprudencePublicationTemporalState(StrEnum):
    PUBLISHED_BY_QUERY_DATE = "published_by_query_date"
    PUBLISHED_AFTER_QUERY_DATE = "published_after_query_date"
    AMBIGUOUS_AT_QUERY_DATE = "ambiguous_at_query_date"
    UNKNOWN = "unknown"


class JurisprudenceBindingTemporalState(StrEnum):
    MANDATORY_BY_QUERY_DATE = "mandatory_by_query_date"
    MANDATORY_AFTER_QUERY_DATE = "mandatory_after_query_date"
    MANDATORY_DATE_AMBIGUOUS = "mandatory_date_ambiguous"
    MANDATORY_DATE_UNKNOWN = "mandatory_date_unknown"
    NOT_JURISPRUDENCE = "not_jurisprudence"


class JurisprudenceTemporalRecord(BaseModel):
    """Contrato E.4: publicación y obligatoriedad temporal de la fuente anexada."""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=3, max_length=200)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    criterion_type: JurisprudenceCriterionType = JurisprudenceCriterionType.UNKNOWN
    publication_date_text: str | None = Field(default=None, max_length=300)
    parsed_publication_start: date | None = None
    parsed_publication_end: date | None = None
    publication_date_precision: JurisprudencePublicationDatePrecision
    publication_date_source_pages: list[int] = Field(default_factory=list, max_length=100)
    binding_character_mandatory: bool
    binding_character_basis: Literal[
        "official_type_jurisprudence",
        "official_type_not_jurisprudence",
        "official_type_unknown",
    ]
    binding_effective_date_text: str | None = Field(default=None, max_length=300)
    parsed_binding_start: date | None = None
    parsed_binding_end: date | None = None
    binding_date_precision: JurisprudencePublicationDatePrecision
    binding_date_source_pages: list[int] = Field(default_factory=list, max_length=100)
    criterion_status_claim: JurisprudenceStatus
    status_claim_source_pages: list[int] = Field(default_factory=list, max_length=100)
    source_scope: Literal["session"] = "session"
    user_attached: Literal[True] = True
    temporal_profile_built: Literal[True] = True
    publication_date_verified: Literal[False] = False
    criterion_status_verified: Literal[False] = False
    normative_temporal_alignment_verified: Literal[False] = False
    binding_force_evaluated: bool
    legal_applicability_evaluated: Literal[False] = False
    can_control_legal_decision: Literal[False] = False

    @model_validator(mode="after")
    def validate_date_intervals(self) -> JurisprudenceTemporalRecord:
        for start, end, precision, label in (
            (
                self.parsed_publication_start,
                self.parsed_publication_end,
                self.publication_date_precision,
                "publicación",
            ),
            (
                self.parsed_binding_start,
                self.parsed_binding_end,
                self.binding_date_precision,
                "obligatoriedad",
            ),
        ):
            if (start is None) != (end is None):
                raise ValueError(f"E.4 requiere inicio y fin de {label} conjuntamente.")
            if start is not None and end is not None and start > end:
                raise ValueError(f"El intervalo de {label} E.4 es inválido.")
            parsed = precision in {
                JurisprudencePublicationDatePrecision.DAY,
                JurisprudencePublicationDatePrecision.MONTH,
                JurisprudencePublicationDatePrecision.YEAR,
            }
            if parsed and start is None:
                raise ValueError(f"Una precisión de {label} conocida requiere fechas.")
            if not parsed and start is not None:
                raise ValueError(
                    f"Una fecha de {label} desconocida o inválida no puede tener intervalo."
                )
        if self.binding_character_mandatory and (
            self.criterion_type is not JurisprudenceCriterionType.JURISPRUDENCE
        ):
            raise ValueError("Sólo el tipo oficial Jurisprudencia activa obligatoriedad E.4.")
        return self


class JurisprudenceTemporalAssessment(BaseModel):
    """E.4 evalúa publicación y obligatoriedad temporal, no aplicabilidad material."""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=3, max_length=200)
    query_date: date
    publication_state: JurisprudencePublicationTemporalState
    published_by_query_date: bool | None
    binding_state: JurisprudenceBindingTemporalState
    binding_character_mandatory: bool
    mandatory_by_query_date: bool | None
    temporally_eligible_for_evidence: bool
    criterion_status_claim: JurisprudenceStatus
    status_claim_treated_as_verified: Literal[False] = False
    legal_applicability_evaluated: Literal[False] = False
    can_control_legal_decision: Literal[False] = False
    requires_human_review: bool
    reasons: list[str] = Field(default_factory=list, min_length=1, max_length=30)
    temporal_control_completed: Literal[True] = True
