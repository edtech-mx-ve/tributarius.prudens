from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.cbr_h1_contrast import CBRAnalogicalEffect
from app.domain.hybrid_coordination import HybridReasoningRelation
from app.domain.hybrid_legal_coordination import H1CoordinationDisposition
from app.domain.hybrid_legal_verification import HybridLegalVerificationState
from app.domain.integral_legal_analysis import IntegralLegalAnalysis
from app.domain.jurisprudence_decision_application import JurisprudenceDecisionEffect


class HybridAnalyzerProjection(BaseModel):
    """Proyección F.8 del argumento híbrido ya verificado por F.7.

    No reabre H1/H2, RBS, CBR ni E.6. Sólo conserva, de forma auditable,
    aquello que Analyzer necesita para la siguiente etapa de cierre jurídico.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    verification_state: HybridLegalVerificationState
    verification_packet_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    canonical_conclusion: str | None = Field(default=None, max_length=4000)

    reasoning_controller: Literal["rbs"] | None = None
    legal_authority_source: Literal["normative_evidence"] | None = None
    applicable_normative_refs: list[str] = Field(default_factory=list, max_length=100)

    h1_hypothesis_id: str | None = Field(default=None, pattern=r"^H1-[a-f0-9]{16}$")
    h1_disposition: H1CoordinationDisposition = H1CoordinationDisposition.NOT_PRESENT
    rbs_h1_relation: HybridReasoningRelation | None = None
    cbr_h1_effect: CBRAnalogicalEffect | None = None
    h2_ratio_ids: list[str] = Field(default_factory=list, max_length=20)

    jurisprudence_effect: JurisprudenceDecisionEffect = JurisprudenceDecisionEffect.NO_EFFECT
    binding_interpretation_required: bool = False
    binding_jurisprudence_document_ids: list[str] = Field(
        default_factory=list,
        max_length=20,
    )
    binding_jurisprudence_evidence_refs: list[str] = Field(
        default_factory=list,
        max_length=100,
    )

    correction_codes: list[str] = Field(default_factory=list, max_length=40)
    review_codes: list[str] = Field(default_factory=list, max_length=40)
    semantic_verification_performed: bool = False
    requires_correction: bool = False
    requires_human_review: bool = False
    analyzer_may_close: bool = False

    source_verification_consumed: Literal[True] = True
    source_results_already_computed: Literal[True] = True
    h1_reexecuted: Literal[False] = False
    h2_reexecuted: Literal[False] = False
    rbs_reexecuted: Literal[False] = False
    cbr_reexecuted: Literal[False] = False
    e6_application_recomputed: Literal[False] = False
    canonical_conclusion_reconstructed: Literal[False] = False
    creates_second_conclusion: Literal[False] = False
    legal_decision_created: Literal[False] = False
    can_control_legal_decision: Literal[False] = False

    @model_validator(mode="after")
    def validate_projection(self) -> HybridAnalyzerProjection:
        if len(self.applicable_normative_refs) != len(set(self.applicable_normative_refs)):
            raise ValueError("F.8 no admite referencias normativas duplicadas.")
        if len(self.h2_ratio_ids) != len(set(self.h2_ratio_ids)):
            raise ValueError("F.8 no admite ratio_ids duplicados.")
        if len(self.binding_jurisprudence_document_ids) != len(
            set(self.binding_jurisprudence_document_ids)
        ):
            raise ValueError("F.8 no admite jurisprudencia vinculante duplicada.")
        if len(self.binding_jurisprudence_evidence_refs) != len(
            set(self.binding_jurisprudence_evidence_refs)
        ):
            raise ValueError("F.8 no admite evidencia jurisprudencial duplicada.")

        if self.verification_state is HybridLegalVerificationState.VERIFIED:
            if self.requires_correction or self.requires_human_review:
                raise ValueError("F.8 VERIFIED no puede conservar bloqueos pendientes.")
        elif self.verification_state is HybridLegalVerificationState.CORRECTION_REQUIRED:
            if not self.requires_correction:
                raise ValueError("F.8 debe preservar el bloqueo CORRECTION_REQUIRED de F.7.")
        elif not self.requires_human_review:
            raise ValueError("F.8 debe preservar HUMAN_REVIEW de F.7.")

        if (
            self.analyzer_may_close
            and self.verification_state is not HybridLegalVerificationState.VERIFIED
        ):
            raise ValueError("F.8 sólo puede permitir cierre cuando F.7 está VERIFIED.")

        expected_binding = (
            self.jurisprudence_effect
            is JurisprudenceDecisionEffect.GOVERNING_INTERPRETATION
        )
        if self.binding_interpretation_required != expected_binding:
            raise ValueError("F.8 presenta un efecto jurisprudencial inconsistente.")
        if expected_binding and not self.binding_jurisprudence_document_ids:
            raise ValueError("La interpretación gobernante exige jurisprudencia identificada.")
        if self.binding_jurisprudence_document_ids and not expected_binding:
            raise ValueError("No puede haber jurisprudencia vinculante sin efecto gobernante.")
        return self


class HybridIntegralLegalAnalysis(IntegralLegalAnalysis):
    """Analyzer F.8: Analyzer 1.0 + proyección inmutable de F.7.

    Es un contrato aditivo. Analyzer 1.0 permanece disponible sin cambios para
    preservar compatibilidad; este modelo es la entrada prevista para F.9.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.1"
    source_analyzer_schema_version: str = "1.0"
    hybrid_projection: HybridAnalyzerProjection
    requires_correction: bool = False
    hybrid_verification_consumed: Literal[True] = True
    source_results_reexecuted: Literal[False] = False
    canonical_conclusion_reconstructed: Literal[False] = False
    creates_second_conclusion: Literal[False] = False
    legal_decision_created: Literal[False] = False
    can_control_legal_decision: Literal[False] = False
