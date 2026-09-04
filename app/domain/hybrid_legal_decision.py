from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.cbr_h1_contrast import CBRAnalogicalEffect
from app.domain.hybrid_coordination import HybridReasoningRelation
from app.domain.hybrid_legal_coordination import H1CoordinationDisposition
from app.domain.hybrid_legal_verification import HybridLegalVerificationState
from app.domain.integral_legal_analysis import IntegralLegalIssue
from app.domain.integral_legal_evidence import IntegralLegalEvidenceMap
from app.domain.integral_legal_readiness import LegalAnalysisReadiness
from app.domain.isr import ISRCalculationResult
from app.domain.jurisprudence_decision_application import (
    JurisprudenceDecisionApplicationRecord,
    JurisprudenceDecisionEffect,
)
from app.domain.legal_consequences import LegalConsequences
from app.domain.legal_fact_assessment import LegalFactAssessment
from app.domain.legal_reasoning_chain import LegalReasoningChain
from app.domain.query import ExtractedFact, MissingField
from app.domain.rules import RuleConclusion


class HybridLegalDecisionStatus(StrEnum):
    """Estado F.9 del cierre jurídico híbrido."""

    DETERMINED = "determined"
    CONDITIONALLY_DETERMINED = "conditionally_determined"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CORRECTION_REQUIRED = "correction_required"
    HUMAN_REVIEW_REQUIRED = "human_review_required"


class HybridLegalDecisionProjection(BaseModel):
    """Proyección F.9 de autoridad, verificación y trazabilidad.

    F.9 no vuelve a decidir el caso. Formaliza, o bloquea formalmente, el
    resultado consolidado por Analyzer F.8. La norma sigue siendo la fuente de
    autoridad jurídica y la jurisprudencia obligatoria aplicable sólo gobierna
    la interpretación de esa base normativa.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    source_analysis_schema_version: str = "1.1"
    source_verification_packet_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    verification_state: HybridLegalVerificationState

    source_canonical_conclusion: str | None = Field(default=None, max_length=4000)
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
    binding_interpretation: Literal["jurisprudence"] | None = None
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
    requires_correction: bool = False
    requires_human_review: bool = False
    closes_automatically: bool = False

    source_hybrid_analysis_consumed: Literal[True] = True
    source_results_already_computed: Literal[True] = True
    h1_reexecuted: Literal[False] = False
    h2_reexecuted: Literal[False] = False
    rbs_reexecuted: Literal[False] = False
    cbr_reexecuted: Literal[False] = False
    jurisprudence_recomputed: Literal[False] = False
    verification_reexecuted: Literal[False] = False
    analyzer_reexecuted: Literal[False] = False

    normative_basis_preserved: Literal[True] = True
    h1_h2_used_as_legal_authority: Literal[False] = False
    cbr_used_as_legal_authority: Literal[False] = False
    jurisprudence_replaces_normative_basis: Literal[False] = False
    jurisprudence_creates_second_conclusion: Literal[False] = False
    single_determination_preserved: Literal[True] = True
    second_conclusion_created: Literal[False] = False

    @model_validator(mode="after")
    def validate_projection(self) -> HybridLegalDecisionProjection:
        if len(self.applicable_normative_refs) != len(set(self.applicable_normative_refs)):
            raise ValueError("F.9 no admite referencias normativas duplicadas.")
        if len(self.h2_ratio_ids) != len(set(self.h2_ratio_ids)):
            raise ValueError("F.9 no admite ratio_ids duplicados.")
        if len(self.binding_jurisprudence_document_ids) != len(
            set(self.binding_jurisprudence_document_ids)
        ):
            raise ValueError("F.9 no admite jurisprudencia vinculante duplicada.")
        if len(self.binding_jurisprudence_evidence_refs) != len(
            set(self.binding_jurisprudence_evidence_refs)
        ):
            raise ValueError("F.9 no admite evidencia jurisprudencial duplicada.")

        expected_binding = (
            self.jurisprudence_effect
            is JurisprudenceDecisionEffect.GOVERNING_INTERPRETATION
        )
        if self.binding_interpretation_required != expected_binding:
            raise ValueError("F.9 presenta un efecto jurisprudencial inconsistente.")
        if expected_binding:
            if self.binding_interpretation != "jurisprudence":
                raise ValueError(
                    "La interpretación gobernante debe identificarse como jurisprudencia."
                )
            if not self.binding_jurisprudence_document_ids:
                raise ValueError("F.9 exige identificar la jurisprudencia gobernante.")
            if not self.binding_jurisprudence_evidence_refs:
                raise ValueError("F.9 exige evidencia para la jurisprudencia gobernante.")
        elif self.binding_interpretation is not None:
            raise ValueError("No puede existir interpretación vinculante sin efecto gobernante.")

        if self.verification_state is HybridLegalVerificationState.VERIFIED:
            if self.requires_correction or self.correction_codes or self.review_codes:
                raise ValueError("F.9 VERIFIED no puede conservar bloqueos de F.7.")
        elif self.verification_state is HybridLegalVerificationState.CORRECTION_REQUIRED:
            if not self.requires_correction:
                raise ValueError("F.9 debe preservar CORRECTION_REQUIRED de F.8.")
        elif not self.requires_human_review:
            raise ValueError("F.9 debe preservar HUMAN_REVIEW de F.8.")

        if self.closes_automatically:
            if self.verification_state is not HybridLegalVerificationState.VERIFIED:
                raise ValueError("F.9 sólo puede cerrar automáticamente una cadena VERIFIED.")
            if self.legal_authority_source != "normative_evidence":
                raise ValueError("F.9 exige evidencia normativa como autoridad del cierre.")
            if not self.applicable_normative_refs:
                raise ValueError("F.9 no puede cerrar sin fundamento normativo aplicable.")
        return self


class HybridLegalDecision(BaseModel):
    """Legal Decision F.9, derivada exclusivamente de Analyzer F.8."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.1"
    source_analysis_schema_version: str = Field(max_length=20)
    source_legacy_decision_schema_version: str = "1.0"

    issue: IntegralLegalIssue
    facts: list[ExtractedFact] = Field(default_factory=list, max_length=40)
    fact_assessments: list[LegalFactAssessment] = Field(default_factory=list, max_length=60)
    reasoning_chain: LegalReasoningChain = Field(default_factory=LegalReasoningChain)
    consequences: LegalConsequences = Field(default_factory=LegalConsequences)
    missing_fields: list[MissingField] = Field(default_factory=list, max_length=20)
    ambiguities: list[str] = Field(default_factory=list, max_length=20)
    applicable_normative_refs: list[str] = Field(default_factory=list, max_length=100)
    rule_conclusions: list[RuleConclusion] = Field(default_factory=list, max_length=100)
    calculation: ISRCalculationResult | None = None

    conclusion: str | None = Field(default=None, max_length=4000)
    controlling_source: Literal["normative_evidence"] | None = None
    analysis_priority: list[str] = Field(default_factory=list, max_length=100)
    evidence_map: IntegralLegalEvidenceMap
    jurisprudence_application: JurisprudenceDecisionApplicationRecord | None = None
    readiness: LegalAnalysisReadiness

    requires_correction: bool = False
    requires_human_review: bool = False
    status: HybridLegalDecisionStatus
    hybrid_projection: HybridLegalDecisionProjection

    hybrid_analysis_consumed: Literal[True] = True
    source_results_reexecuted: Literal[False] = False
    canonical_conclusion_reconstructed: Literal[False] = False
    creates_second_conclusion: Literal[False] = False
    legal_authority_reassigned_by_llm: Literal[False] = False

    @model_validator(mode="after")
    def validate_decision(self) -> HybridLegalDecision:
        projection = self.hybrid_projection

        if self.source_analysis_schema_version != projection.source_analysis_schema_version:
            raise ValueError("F.9 presenta versiones de Analyzer inconsistentes.")
        if self.applicable_normative_refs != projection.applicable_normative_refs:
            raise ValueError("F.9 debe preservar exactamente la base normativa de F.8.")
        if self.requires_correction != projection.requires_correction:
            raise ValueError("F.9 debe preservar el bloqueo de corrección de F.8.")
        if self.requires_human_review != projection.requires_human_review:
            raise ValueError("F.9 debe preservar la revisión humana de F.8.")

        determined = self.status in {
            HybridLegalDecisionStatus.DETERMINED,
            HybridLegalDecisionStatus.CONDITIONALLY_DETERMINED,
        }
        if determined:
            if self.conclusion is None:
                raise ValueError("F.9 no puede determinar sin conclusión canónica.")
            if self.conclusion != projection.source_canonical_conclusion:
                raise ValueError("F.9 no puede crear una conclusión distinta de F.8.")
            if self.controlling_source != "normative_evidence":
                raise ValueError("F.9 debe conservar la norma como autoridad jurídica.")
            if projection.legal_authority_source != "normative_evidence":
                raise ValueError("F.8 no autorizó una base normativa para el cierre.")
            if not self.applicable_normative_refs:
                raise ValueError("F.9 no puede determinar sin referencias normativas.")
        else:
            if self.conclusion is not None:
                raise ValueError("F.9 no formaliza conclusión cuando el cierre está bloqueado.")
            if self.controlling_source is not None:
                raise ValueError("F.9 no asigna autoridad controladora sin determinación.")

        if self.status is HybridLegalDecisionStatus.DETERMINED:
            if not projection.closes_automatically:
                raise ValueError("F.9 DETERMINED exige cierre automático autorizado por F.8.")
        elif projection.closes_automatically:
            raise ValueError("F.9 no puede bloquear una cadena apta para cierre automático.")

        if self.status is HybridLegalDecisionStatus.CORRECTION_REQUIRED:
            if not self.requires_correction or self.requires_human_review:
                raise ValueError("F.9 debe diferenciar corrección de revisión humana.")
        if self.status is HybridLegalDecisionStatus.HUMAN_REVIEW_REQUIRED:
            if not self.requires_human_review:
                raise ValueError("F.9 HUMAN_REVIEW_REQUIRED exige revisión humana.")

        return self
