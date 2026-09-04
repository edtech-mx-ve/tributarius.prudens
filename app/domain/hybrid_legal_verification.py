from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.cbr_h1_contrast import CBRH1ContrastResult
from app.domain.hybrid_legal_coordination import HybridLegalCoordinationResult
from app.domain.hybrid_llama_hypotheses import (
    FiscalHypothesisH1Result,
    JurisprudentialRatioH2Result,
)
from app.domain.jurisprudence_decision_application import (
    JurisprudenceDecisionApplicationRecord,
)
from app.domain.llama_hybrid_context import (
    InitialFiscalHypothesisContext,
    JurisprudentialRatioContext,
    PostDeterministicHybridReviewContext,
)
from app.domain.rbs_h1_contrast import RBSH1ContrastResult


class HybridLegalVerificationState(StrEnum):
    """Resultado final F.7 del control híbrido."""

    VERIFIED = "verified"
    CORRECTION_REQUIRED = "correction_required"
    HUMAN_REVIEW = "human_review"


class HybridVerificationCheckOutcome(StrEnum):
    """Resultado de una comprobación individual F.7."""

    PASS = "pass"
    FAIL = "fail"
    REVIEW = "review"
    NOT_APPLICABLE = "not_applicable"


class HybridSemanticAssessment(StrEnum):
    """Juicio semántico controlado emitido por el verificador generativo."""

    CONSISTENT = "consistent"
    INCONSISTENT = "inconsistent"
    UNRESOLVED = "unresolved"
    NOT_APPLICABLE = "not_applicable"


class HybridVerificationCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=3, max_length=120)
    outcome: HybridVerificationCheckOutcome
    detail: str = Field(min_length=1, max_length=1200)
    refs: list[str] = Field(default_factory=list, max_length=100)


class H2SemanticVerificationDraft(BaseModel):
    """Evaluación semántica restringida de una H2 ya controlada en F.3."""

    model_config = ConfigDict(extra="forbid")

    ratio_id: str = Field(pattern=r"^H2-[a-f0-9]{16}$")
    source_fidelity: HybridSemanticAssessment
    consistency_with_coordinated_argument: HybridSemanticAssessment


class HybridLegalSemanticVerificationDraft(BaseModel):
    """Salida generativa F.7 que sólo audita; nunca redacta otra decisión."""

    model_config = ConfigDict(extra="forbid")

    packet_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    h1_consistency: HybridSemanticAssessment
    rbs_representation: HybridSemanticAssessment
    cbr_role: HybridSemanticAssessment
    h2_assessments: list[H2SemanticVerificationDraft] = Field(
        default_factory=list,
        max_length=20,
    )
    binding_jurisprudence_consistency: HybridSemanticAssessment
    contradiction_codes: list[str] = Field(default_factory=list, max_length=20)
    hallucination_signals: list[str] = Field(default_factory=list, max_length=20)
    requires_human_review: bool = False
    changes_canonical_conclusion: Literal[False] = False
    introduces_new_facts: Literal[False] = False
    introduces_new_normative_refs: Literal[False] = False
    introduces_external_jurisprudence: Literal[False] = False
    can_control_legal_decision: Literal[False] = False

    @model_validator(mode="after")
    def validate_unique_ratio_ids(self) -> HybridLegalSemanticVerificationDraft:
        ratio_ids = [item.ratio_id for item in self.h2_assessments]
        if len(ratio_ids) != len(set(ratio_ids)):
            raise ValueError("F.7 no admite evaluaciones H2 duplicadas.")
        return self


class HybridLegalVerificationPacket(BaseModel):
    """Snapshot inmutable de entradas ya calculadas que F.7 puede auditar."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    coordination: HybridLegalCoordinationResult | None = None
    initial_context: InitialFiscalHypothesisContext | None = None
    h1_result: FiscalHypothesisH1Result | None = None
    rbs_h1_contrast: RBSH1ContrastResult | None = None
    cbr_h1_contrast: CBRH1ContrastResult | None = None
    h2_results: list[JurisprudentialRatioH2Result] = Field(default_factory=list, max_length=20)
    jurisprudence_ratio_contexts: list[JurisprudentialRatioContext] = Field(
        default_factory=list,
        max_length=20,
    )
    jurisprudence_application: JurisprudenceDecisionApplicationRecord | None = None
    post_deterministic_context: PostDeterministicHybridReviewContext | None = None
    source_results_already_computed: Literal[True] = True
    legal_decision_included: Literal[False] = False
    may_verify_only: Literal[True] = True
    may_reexecute_sources: Literal[False] = False
    can_change_canonical_conclusion: Literal[False] = False
    can_control_legal_decision: Literal[False] = False

    @model_validator(mode="after")
    def validate_unique_context_documents(self) -> HybridLegalVerificationPacket:
        document_ids = [item.document_id for item in self.jurisprudence_ratio_contexts]
        if len(document_ids) != len(set(document_ids)):
            raise ValueError("F.7 no admite contextos jurisprudenciales duplicados.")
        return self


class HybridLegalVerificationResult(BaseModel):
    """Resultado F.7: auditoría, no una segunda determinación jurídica."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    state: HybridLegalVerificationState
    packet_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    canonical_conclusion: str | None = Field(default=None, max_length=4000)
    h1_hypothesis_id: str | None = Field(default=None, pattern=r"^H1-[a-f0-9]{16}$")
    h2_ratio_ids: list[str] = Field(default_factory=list, max_length=20)

    checks: list[HybridVerificationCheck] = Field(default_factory=list, max_length=80)
    h1_context_integrity_verified: bool | None = None
    h1_fact_boundary_verified: bool | None = None
    h1_normative_boundary_verified: bool | None = None
    rbs_priority_preserved: bool = False
    cbr_experiential_role_preserved: bool = False
    h2_source_fidelity_verified: bool | None = None
    h2_normative_boundary_verified: bool | None = None
    binding_jurisprudence_respected: bool = False
    normative_basis_preserved: bool = False
    single_conclusion_preserved: bool = False

    semantic_verification_performed: bool = False
    semantic_verifier_provider: str | None = Field(default=None, max_length=100)
    semantic_verifier_model: str | None = Field(default=None, max_length=200)
    semantic_draft: HybridLegalSemanticVerificationDraft | None = None
    semantic_equivalence_inferred_deterministically: Literal[False] = False

    h1_generation_reexecuted: Literal[False] = False
    h2_generation_reexecuted: Literal[False] = False
    rbs_reexecuted: Literal[False] = False
    cbr_reexecuted: Literal[False] = False
    e6_application_recomputed: Literal[False] = False
    facts_mutated: Literal[False] = False
    normative_refs_mutated: Literal[False] = False
    ratio_mutated: Literal[False] = False
    canonical_conclusion_mutated: Literal[False] = False
    creates_second_conclusion: Literal[False] = False
    can_control_legal_decision: Literal[False] = False

    correction_codes: list[str] = Field(default_factory=list, max_length=40)
    review_codes: list[str] = Field(default_factory=list, max_length=40)
    requires_human_review: bool = False
    trace: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_final_state(self) -> HybridLegalVerificationResult:
        if len(self.h2_ratio_ids) != len(set(self.h2_ratio_ids)):
            raise ValueError("F.7 no admite ratio_ids duplicados.")
        if len(self.correction_codes) != len(set(self.correction_codes)):
            raise ValueError("F.7 no admite códigos de corrección duplicados.")
        if len(self.review_codes) != len(set(self.review_codes)):
            raise ValueError("F.7 no admite códigos de revisión duplicados.")
        if self.state is HybridLegalVerificationState.VERIFIED:
            if self.correction_codes or self.review_codes or self.requires_human_review:
                raise ValueError("F.7 VERIFIED no puede conservar incidencias pendientes.")
        if self.state is HybridLegalVerificationState.CORRECTION_REQUIRED:
            if not self.correction_codes:
                raise ValueError("F.7 CORRECTION_REQUIRED exige una causa verificable.")
        if self.state is HybridLegalVerificationState.HUMAN_REVIEW:
            if not self.review_codes:
                raise ValueError("F.7 HUMAN_REVIEW exige una causa de revisión.")
        return self
