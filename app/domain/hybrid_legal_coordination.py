from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.cbr_h1_contrast import CBRAnalogicalEffect
from app.domain.hybrid_coordination import HybridReasoningRelation
from app.domain.jurisprudence_decision_application import JurisprudenceDecisionEffect


class HybridLegalCoordinationState(StrEnum):
    """Estado F.6 de la coordinación argumentativa híbrida."""

    NOT_READY = "not_ready"
    COORDINATED = "coordinated"
    REVIEW_REQUIRED = "review_required"


class H1CoordinationDisposition(StrEnum):
    """Cómo queda H1 después del contraste determinativo RBS.

    El CBR puede aportar apoyo, límite o distinción, pero no cambia esta
    disposición porque su función es experiencial y no determinativa.
    """

    NOT_PRESENT = "not_present"
    CONFIRMED = "confirmed"
    CORRECTED = "corrected"
    CONTRADICTED = "contradicted"
    LIMITED_BY_EXCEPTION = "limited_by_exception"
    UNRESOLVED = "unresolved"


class H2HybridCoordinationLink(BaseModel):
    """Vínculo trazable entre una H2 y el resultado jurisprudencial E.6.

    F.6 no vuelve a reconstruir la ratio ni reevalúa la aplicabilidad. Sólo
    enlaza la hipótesis H2 con los resultados deterministas ya existentes para
    que F.7 pueda verificar fidelidad y consistencia posteriormente.
    """

    model_config = ConfigDict(extra="forbid")

    ratio_id: str = Field(pattern=r"^H2-[a-f0-9]{16}$")
    document_id: str = Field(min_length=3, max_length=200)
    interpreted_normative_refs: list[str] = Field(default_factory=list, max_length=100)
    shared_applicable_normative_refs: list[str] = Field(
        default_factory=list, max_length=100
    )
    linked_to_e6_assessment: bool = False
    e6_decision_effect: JurisprudenceDecisionEffect = JurisprudenceDecisionEffect.NO_EFFECT
    binding_jurisprudence_applies: bool = False
    ratio_source_is_justification: Literal[True] = True
    ratio_fidelity_reverified: Literal[False] = False
    consistency_with_h1_rbs_cbr_evaluated: Literal[False] = False
    h2_used_as_legal_authority: Literal[False] = False
    requires_later_verification: Literal[True] = True

    @model_validator(mode="after")
    def validate_e6_link(self) -> H2HybridCoordinationLink:
        if self.binding_jurisprudence_applies:
            if not self.linked_to_e6_assessment:
                raise ValueError("H2 no puede declarar obligatoriedad sin vínculo E.6.")
            if self.e6_decision_effect is not JurisprudenceDecisionEffect.GOVERNING_INTERPRETATION:
                raise ValueError(
                    "La jurisprudencia obligatoria aplicable debe gobernar interpretación."
                )
        if len(self.interpreted_normative_refs) != len(set(self.interpreted_normative_refs)):
            raise ValueError("F.6 no admite normas H2 duplicadas.")
        if len(self.shared_applicable_normative_refs) != len(
            set(self.shared_applicable_normative_refs)
        ):
            raise ValueError("F.6 no admite normas compartidas H2 duplicadas.")
        return self


class HybridLegalCoordinationResult(BaseModel):
    """Coordinación F.6 de H1, RBS, CBR, H2, normas y jurisprudencia.

    Este contrato no crea una nueva determinación jurídica. Conserva la
    conclusión canónica del coordinador RBS-CBR existente, registra cómo RBS
    trató H1, incorpora el CBR sólo como contraste experiencial y respeta el
    efecto interpretativo obligatorio que E.6 ya haya establecido.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    state: HybridLegalCoordinationState
    canonical_conclusion: str | None = Field(default=None, max_length=4000)
    reasoning_controller: Literal["rbs"] | None = None
    legal_authority_source: Literal["normative_evidence"] | None = None
    applicable_normative_refs: list[str] = Field(default_factory=list, max_length=100)
    existing_rbs_cbr_relation: HybridReasoningRelation | None = None

    h1_hypothesis_id: str | None = Field(default=None, pattern=r"^H1-[a-f0-9]{16}$")
    h1_disposition: H1CoordinationDisposition = H1CoordinationDisposition.NOT_PRESENT
    rbs_h1_relation: HybridReasoningRelation | None = None
    cbr_h1_effect: CBRAnalogicalEffect | None = None
    rbs_h1_requires_review: bool = False
    cbr_h1_requires_review: bool = False

    h2_links: list[H2HybridCoordinationLink] = Field(default_factory=list, max_length=20)
    jurisprudence_effect: JurisprudenceDecisionEffect = JurisprudenceDecisionEffect.NO_EFFECT
    binding_interpretation_required: bool = False
    binding_jurisprudence_document_ids: list[str] = Field(
        default_factory=list, max_length=20
    )
    binding_jurisprudence_evidence_refs: list[str] = Field(
        default_factory=list, max_length=100
    )

    verification_required: bool = False
    conclusion_consistency_evaluated: Literal[False] = False
    existing_hybrid_coordination_preserved: Literal[True] = True
    rbs_reexecuted: Literal[False] = False
    cbr_reexecuted: Literal[False] = False
    e6_application_recomputed: Literal[False] = False
    weighted_score_aggregation_used: Literal[False] = False
    majority_vote_used: Literal[False] = False
    cbr_can_override_rbs: Literal[False] = False
    h1_used_as_legal_authority: Literal[False] = False
    h2_used_as_legal_authority: Literal[False] = False
    normative_basis_preserved: Literal[True] = True
    jurisprudence_replaces_normative_basis: Literal[False] = False
    jurisprudence_creates_second_conclusion: Literal[False] = False
    single_conclusion_preserved: Literal[True] = True
    can_control_legal_decision: Literal[False] = False

    reasons: list[str] = Field(default_factory=list, max_length=40)
    requires_human_review: bool = False
    trace: list[str] = Field(default_factory=list, max_length=80)

    @model_validator(mode="after")
    def validate_coordination_boundary(self) -> HybridLegalCoordinationResult:
        if len(self.applicable_normative_refs) != len(set(self.applicable_normative_refs)):
            raise ValueError("F.6 no admite referencias normativas duplicadas.")
        if len(self.binding_jurisprudence_document_ids) != len(
            set(self.binding_jurisprudence_document_ids)
        ):
            raise ValueError("F.6 no admite jurisprudencia vinculante duplicada.")
        if len(self.binding_jurisprudence_evidence_refs) != len(
            set(self.binding_jurisprudence_evidence_refs)
        ):
            raise ValueError("F.6 no admite evidencia jurisprudencial duplicada.")

        if self.state is HybridLegalCoordinationState.NOT_READY:
            if self.canonical_conclusion is not None:
                raise ValueError("F.6 NOT_READY no puede presentar conclusión canónica.")
        elif self.canonical_conclusion is None:
            raise ValueError("F.6 coordinado requiere una conclusión determinista previa.")

        if self.reasoning_controller == "rbs" and self.canonical_conclusion is None:
            raise ValueError("RBS no puede controlar una conclusión inexistente.")
        if (
            self.legal_authority_source == "normative_evidence"
            and not self.applicable_normative_refs
        ):
            raise ValueError("La autoridad normativa exige referencias aplicables verificadas.")

        expected_binding = (
            self.jurisprudence_effect
            is JurisprudenceDecisionEffect.GOVERNING_INTERPRETATION
        )
        if self.binding_interpretation_required != expected_binding:
            raise ValueError("F.6 presenta efecto jurisprudencial inconsistente.")
        if expected_binding and not self.binding_jurisprudence_document_ids:
            raise ValueError("La interpretación gobernante exige jurisprudencia identificada.")
        if self.binding_jurisprudence_document_ids and not expected_binding:
            raise ValueError("No puede existir jurisprudencia vinculante sin efecto gobernante.")

        if self.h1_disposition is H1CoordinationDisposition.NOT_PRESENT:
            if self.h1_hypothesis_id is not None:
                raise ValueError("H1 NOT_PRESENT no puede conservar hypothesis_id.")
        elif self.h1_hypothesis_id is None:
            raise ValueError("La disposición de H1 requiere hypothesis_id.")

        return self
