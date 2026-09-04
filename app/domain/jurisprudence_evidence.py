from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.jurisprudence import JurisprudenceStatus, NormRelationType
from app.domain.jurisprudence_temporal import (
    JurisprudenceBindingTemporalState,
    JurisprudencePublicationTemporalState,
)


class JurisprudenceEvidenceDecision(StrEnum):
    ADMITTED = "admitted"
    REVIEW_ONLY = "review_only"
    REJECTED = "rejected"


class JurisprudenceEvidenceAssessment(BaseModel):
    """E.5 decide admisión como evidencia, no aplicabilidad jurídica definitiva."""

    model_config = ConfigDict(extra="forbid")

    evidence_ref: str = Field(min_length=3, max_length=300)
    document_id: str = Field(min_length=3, max_length=200)
    page_number: int = Field(ge=1)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    retrieval_score: float = Field(ge=0.0, le=1.0)
    decision: JurisprudenceEvidenceDecision
    authorized_for_evidence: bool
    shared_normative_refs: list[str] = Field(default_factory=list, max_length=100)
    explicit_material_relation_refs: list[str] = Field(
        default_factory=list,
        max_length=100,
    )
    material_relation_types: list[NormRelationType] = Field(
        default_factory=list,
        max_length=10,
    )
    temporal_state: JurisprudencePublicationTemporalState
    binding_state: JurisprudenceBindingTemporalState
    binding_character_mandatory: bool
    mandatory_by_query_date: bool | None
    temporally_eligible: bool
    structured_thesis_sections_established: bool
    ratio_source_established: bool
    ratio_page_contains_justification: bool
    justification_normative_relevance_established: bool
    criterion_status_claim: JurisprudenceStatus
    problem_relevance_established: bool
    normative_relevance_established: bool
    material_normative_relation_established: bool
    source_scope: Literal["session"] = "session"
    user_attached: Literal[True] = True
    normative_evidence_preserved: Literal[True] = True
    jurisprudence_does_not_replace_normative_evidence: Literal[True] = True
    evidence_admission_evaluated: Literal[True] = True
    legal_applicability_determined: Literal[False] = False
    binding_force_evaluated: bool
    can_control_legal_decision: Literal[False] = False
    requires_human_review: bool
    reasons: list[str] = Field(default_factory=list, min_length=1, max_length=30)

    @model_validator(mode="after")
    def validate_admission_boundary(self) -> JurisprudenceEvidenceAssessment:
        if self.authorized_for_evidence != (
            self.decision is JurisprudenceEvidenceDecision.ADMITTED
        ):
            raise ValueError("La decisión E.5 y la admisión de evidencia son inconsistentes.")
        if self.authorized_for_evidence:
            if not self.temporally_eligible:
                raise ValueError("E.5 no puede admitir evidencia temporalmente inelegible.")
            if not self.problem_relevance_established:
                raise ValueError("E.5 requiere relevancia respecto del problema consultado.")
            if not self.normative_relevance_established:
                raise ValueError("E.5 requiere relación con norma aplicable recuperada.")
            if not self.material_normative_relation_established:
                raise ValueError("E.5 requiere relación normativa material explícita.")
            if not self.binding_character_mandatory:
                raise ValueError(
                    "E.5 sólo admite como jurisprudencia obligatoria "
                    "el tipo oficial Jurisprudencia."
                )
            if self.mandatory_by_query_date is not True:
                raise ValueError("E.5 requiere que la obligatoriedad ya produzca efectos.")
            if not self.structured_thesis_sections_established:
                raise ValueError(
                    "E.5 requiere Hechos, Criterio jurídico y "
                    "Justificación estructurados."
                )
            if not self.ratio_source_established:
                raise ValueError("E.5 requiere Justificación como fuente de ratio decidendi.")
            if not self.ratio_page_contains_justification:
                raise ValueError(
                    "E.5 sólo admite como evidencia sustantiva páginas "
                    "que contienen la Justificación."
                )
            if not self.justification_normative_relevance_established:
                raise ValueError(
                    "E.5 requiere que la Justificación se relacione "
                    "con la norma aplicable."
                )
        return self


class JurisprudenceEvidenceIntegrationRecord(BaseModel):
    """Contrato E.5: evidencia jurisprudencial admitida de forma diferenciada."""

    model_config = ConfigDict(extra="forbid")

    assessments: list[JurisprudenceEvidenceAssessment] = Field(default_factory=list)
    authorized_evidence_refs: list[str] = Field(default_factory=list, max_length=100)
    admitted_count: int = Field(ge=0)
    review_only_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    evidence_integration_completed: Literal[True] = True
    source_scope: Literal["session"] = "session"
    user_attached: Literal[True] = True
    normative_evidence_preserved: Literal[True] = True
    jurisprudence_is_separate_evidence_layer: Literal[True] = True
    legal_applicability_determined: Literal[False] = False
    binding_force_evaluated: bool
    can_control_legal_decision: Literal[False] = False
    requires_human_review: bool

    @model_validator(mode="after")
    def validate_counts(self) -> JurisprudenceEvidenceIntegrationRecord:
        admitted = sum(
            item.decision is JurisprudenceEvidenceDecision.ADMITTED
            for item in self.assessments
        )
        review_only = sum(
            item.decision is JurisprudenceEvidenceDecision.REVIEW_ONLY
            for item in self.assessments
        )
        rejected = sum(
            item.decision is JurisprudenceEvidenceDecision.REJECTED
            for item in self.assessments
        )
        if admitted != self.admitted_count:
            raise ValueError("Conteo E.5 de evidencia admitida inconsistente.")
        if review_only != self.review_only_count:
            raise ValueError("Conteo E.5 de evidencia en revisión inconsistente.")
        if rejected != self.rejected_count:
            raise ValueError("Conteo E.5 de evidencia rechazada inconsistente.")
        expected_refs = [
            item.evidence_ref for item in self.assessments if item.authorized_for_evidence
        ]
        if expected_refs != self.authorized_evidence_refs:
            raise ValueError("Referencias E.5 autorizadas inconsistentes.")
        return self
