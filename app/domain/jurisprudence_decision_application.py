from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.jurisprudence import NormRelationType


class JurisprudenceCaseApplicationStatus(StrEnum):
    APPLICABLE = "applicable"
    REVIEW_REQUIRED = "review_required"
    NOT_APPLICABLE = "not_applicable"


class JurisprudenceDecisionEffect(StrEnum):
    GOVERNING_INTERPRETATION = "governing_interpretation"
    REVIEW_REQUIRED = "review_required"
    NO_EFFECT = "no_effect"


class JurisprudenceCaseApplicationAssessment(BaseModel):
    """E.6: traslado de la ratio al caso concreto, sin sustituir la norma."""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=3, max_length=200)
    authorized_evidence_refs: list[str] = Field(min_length=1, max_length=100)
    shared_normative_refs: list[str] = Field(min_length=1, max_length=100)
    relation_types: list[NormRelationType] = Field(min_length=1, max_length=10)
    controversy_similarity_score: float = Field(ge=0.0, le=1.0)
    material_fact_similarity_score: float = Field(ge=0.0, le=1.0)
    matched_controversy_terms: list[str] = Field(default_factory=list, max_length=40)
    matched_material_fact_anchors: list[str] = Field(default_factory=list, max_length=40)
    hard_material_conflicts: list[str] = Field(default_factory=list, max_length=20)
    normative_equivalence_established: bool
    controversy_equivalence_established: bool
    material_facts_equivalence_established: bool
    ratio_transfer_established: bool
    status: JurisprudenceCaseApplicationStatus
    decision_effect: JurisprudenceDecisionEffect
    binding_jurisprudence_applies: bool
    must_be_respected_by_legal_decision: bool
    source_scope: Literal["session"] = "session"
    user_attached: Literal[True] = True
    official_jurisprudence_mandatory: Literal[True] = True
    ratio_source_is_justification: Literal[True] = True
    normative_basis_preserved: Literal[True] = True
    can_replace_normative_basis: Literal[False] = False
    can_create_second_conclusion: Literal[False] = False
    can_invent_ratio: Literal[False] = False
    conclusion_consistency_evaluated: Literal[False] = False
    requires_human_review: bool
    reasons: list[str] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def validate_e6_boundary(self) -> JurisprudenceCaseApplicationAssessment:
        expected_applies = self.status is JurisprudenceCaseApplicationStatus.APPLICABLE
        if self.binding_jurisprudence_applies != expected_applies:
            raise ValueError("E.6 presenta un estado de aplicabilidad inconsistente.")
        if self.must_be_respected_by_legal_decision != expected_applies:
            raise ValueError("E.6 no puede separar aplicabilidad y efecto obligatorio.")
        if expected_applies:
            if not self.normative_equivalence_established:
                raise ValueError("E.6 requiere equivalencia normativa para aplicar la ratio.")
            if not self.controversy_equivalence_established:
                raise ValueError("E.6 requiere equivalencia de controversia.")
            if not self.material_facts_equivalence_established:
                raise ValueError("E.6 requiere equivalencia de hechos materiales.")
            if self.hard_material_conflicts:
                raise ValueError("E.6 no puede aplicar jurisprudencia con conflicto material.")
            if self.decision_effect is not JurisprudenceDecisionEffect.GOVERNING_INTERPRETATION:
                raise ValueError("La jurisprudencia aplicable debe gobernar la interpretación.")
        return self


class JurisprudenceDecisionApplicationRecord(BaseModel):
    """Resultado E.6 consumible por Analyzer y Legal Decision."""

    model_config = ConfigDict(extra="forbid")

    assessments: list[JurisprudenceCaseApplicationAssessment] = Field(default_factory=list)
    applicable_document_ids: list[str] = Field(default_factory=list, max_length=20)
    binding_evidence_refs: list[str] = Field(default_factory=list, max_length=100)
    application_evaluated: Literal[True] = True
    analyzer_projection_required: Literal[True] = True
    legal_decision_projection_required: Literal[True] = True
    normative_basis_preserved: Literal[True] = True
    single_conclusion_preserved: Literal[True] = True
    jurisprudence_may_govern_interpretation: Literal[True] = True
    jurisprudence_never_replaces_normative_basis: Literal[True] = True
    requires_human_review: bool

    @model_validator(mode="after")
    def validate_projection(self) -> JurisprudenceDecisionApplicationRecord:
        expected_docs = [
            item.document_id for item in self.assessments if item.binding_jurisprudence_applies
        ]
        expected_refs = [
            ref
            for item in self.assessments
            if item.binding_jurisprudence_applies
            for ref in item.authorized_evidence_refs
        ]
        if self.applicable_document_ids != list(dict.fromkeys(expected_docs)):
            raise ValueError("Documentos jurisprudenciales aplicables inconsistentes.")
        if self.binding_evidence_refs != list(dict.fromkeys(expected_refs)):
            raise ValueError("Evidencia jurisprudencial vinculante inconsistente.")
        return self
