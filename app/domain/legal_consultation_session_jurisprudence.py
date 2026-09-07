from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.jurisprudence_decision_application import (
    JurisprudenceDecisionEffect,
)
from app.domain.jurisprudence_hybrid import SessionJurisprudenceHybridResult
from app.domain.jurisprudence_ratio import JurisprudenceRatioRecord


class LegalConsultationSessionJurisprudence(BaseModel):
    """G.7: jurisprudencia exclusivamente aportada por el usuario en sesion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    user_attached: bool = False
    session_result: SessionJurisprudenceHybridResult | None = None
    ratio_records: list[JurisprudenceRatioRecord] = Field(default_factory=list)

    applicable_document_ids: list[str] = Field(default_factory=list, max_length=20)
    binding_evidence_refs: list[str] = Field(default_factory=list, max_length=100)
    binding_jurisprudence_applies: bool = False
    governing_interpretation: bool = False

    official_jurisprudence_mandatory_when_applicable: Literal[True] = True
    source_scope_session_only: Literal[True] = True
    external_search_performed: Literal[False] = False

    normative_basis_preserved: Literal[True] = True
    single_conclusion_preserved: Literal[True] = True
    can_replace_normative_basis: Literal[False] = False
    can_create_second_conclusion: Literal[False] = False

    @model_validator(mode="after")
    def validate_jurisprudence_boundary(
        self,
    ) -> LegalConsultationSessionJurisprudence:
        ratio_ids = [item.document_id for item in self.ratio_records]
        if len(ratio_ids) != len(set(ratio_ids)):
            raise ValueError(
                "G.7 no admite registros de ratio jurisprudencial duplicados."
            )

        if not self.user_attached:
            if (
                self.session_result is not None
                or self.ratio_records
                or self.applicable_document_ids
                or self.binding_evidence_refs
                or self.binding_jurisprudence_applies
                or self.governing_interpretation
            ):
                raise ValueError(
                    "G.7 no admite jurisprudencia sin adjunto de sesion."
                )
            return self

        if self.session_result is None:
            if (
                self.applicable_document_ids
                or self.binding_evidence_refs
                or self.binding_jurisprudence_applies
                or self.governing_interpretation
            ):
                raise ValueError(
                    "G.7 no puede declarar efecto jurisprudencial sin evaluacion."
                )
            return self

        application = self.session_result.decision_application
        if application is None:
            if (
                self.applicable_document_ids
                or self.binding_evidence_refs
                or self.binding_jurisprudence_applies
                or self.governing_interpretation
            ):
                raise ValueError(
                    "G.7 no puede declarar efecto vinculante sin aplicacion E.6."
                )
            return self

        if self.applicable_document_ids != application.applicable_document_ids:
            raise ValueError(
                "G.7 detecto documentos jurisprudenciales aplicables inconsistentes."
            )

        if self.binding_evidence_refs != application.binding_evidence_refs:
            raise ValueError(
                "G.7 detecto evidencia jurisprudencial vinculante inconsistente."
            )

        expected_binding = bool(application.applicable_document_ids)

        if self.binding_jurisprudence_applies != expected_binding:
            raise ValueError(
                "G.7 presenta un estado vinculante jurisprudencial inconsistente."
            )

        if self.governing_interpretation != expected_binding:
            raise ValueError(
                "G.7 presenta un efecto interpretativo jurisprudencial inconsistente."
            )

        if expected_binding:
            ratios = {
                item.document_id: item
                for item in self.ratio_records
            }

            for document_id in application.applicable_document_ids:
                ratio = ratios.get(document_id)
                if ratio is None or not ratio.ratio_source_established:
                    raise ValueError(
                        "G.7 exige ratio fuente establecida para jurisprudencia aplicable."
                    )

            for assessment in application.assessments:
                if not assessment.binding_jurisprudence_applies:
                    continue
                if (
                    assessment.decision_effect
                    is not JurisprudenceDecisionEffect.GOVERNING_INTERPRETATION
                ):
                    raise ValueError(
                        "G.7 exige interpretacion gobernante cuando la jurisprudencia aplica."
                    )
                if not assessment.must_be_respected_by_legal_decision:
                    raise ValueError(
                        "G.7 exige respetar jurisprudencia obligatoria aplicable."
                    )

        return self
