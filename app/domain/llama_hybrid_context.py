from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.jurisprudence import JurisprudenceCriterionType
from app.domain.jurisprudence_ratio import JurisprudenceRatioSourceSection
from app.domain.query import FactOrigin, QueryIntent


class LlamaHybridContextPhase(StrEnum):
    """Puntos de contexto F.2; todavía no son invocaciones del modelo."""

    INITIAL_FISCAL_HYPOTHESIS = "initial_fiscal_hypothesis"
    JURISPRUDENTIAL_RATIO = "jurisprudential_ratio"
    POST_DETERMINISTIC_REVIEW = "post_deterministic_review"


class LlamaFactSnapshot(BaseModel):
    """Hecho explícito/inferido por Query Analyzer que puede viajar a Llama."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=1000)
    origin: FactOrigin


class LlamaHeuristicRouteContext(BaseModel):
    """Ruta D.1-D.7 como orientación; nunca evidencia de autoridad jurídica."""

    model_config = ConfigDict(extra="forbid")

    primary_problem_id: str | None = Field(default=None, max_length=120)
    primary_problem_label: str | None = Field(default=None, max_length=240)
    primary_institution_id: str | None = Field(default=None, max_length=120)
    primary_institution_label: str | None = Field(default=None, max_length=240)
    primary_manual_entry_ids: list[str] = Field(default_factory=list, max_length=19)
    rbs_orientation_relation_ids: list[str] = Field(default_factory=list, max_length=18)
    rbs_orientation_family_ids: list[str] = Field(default_factory=list, max_length=17)
    cbr_orientation_situation_ids: list[str] = Field(default_factory=list, max_length=20)
    cbr_orientation_family_ids: list[str] = Field(default_factory=list, max_length=12)
    normative_focus_source_ids: list[str] = Field(default_factory=list, max_length=5)
    exact_normative_hints: list[str] = Field(default_factory=list, max_length=200)
    temporal_signal_values: list[str] = Field(default_factory=list, max_length=20)
    unresolved_dimensions: list[str] = Field(default_factory=list, max_length=20)
    orientation_only: Literal[True] = True
    normative_validation_pending: Literal[True] = True
    temporal_validation_pending: Literal[True] = True
    can_control_legal_decision: Literal[False] = False

    @model_validator(mode="after")
    def validate_unique_refs(self) -> LlamaHeuristicRouteContext:
        for values in (
            self.primary_manual_entry_ids,
            self.rbs_orientation_relation_ids,
            self.rbs_orientation_family_ids,
            self.cbr_orientation_situation_ids,
            self.cbr_orientation_family_ids,
            self.normative_focus_source_ids,
            self.exact_normative_hints,
            self.temporal_signal_values,
            self.unresolved_dimensions,
        ):
            if len(values) != len(set(values)):
                raise ValueError("F.2 no admite referencias duplicadas en la ruta heurística.")
        return self


class InitialFiscalHypothesisContext(BaseModel):
    """Contexto temprano que F.3 podrá usar para formular H1.

    Se construye tras Query Analyzer y antes de consumir resultados determinativos
    de RBS/CBR. Las pistas D sólo sirven para orientar qué debe investigarse.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    phase: Literal[LlamaHybridContextPhase.INITIAL_FISCAL_HYPOTHESIS] = (
        LlamaHybridContextPhase.INITIAL_FISCAL_HYPOTHESIS
    )
    question: str = Field(min_length=1, max_length=4000)
    normalized_query: str = Field(min_length=1, max_length=4000)
    primary_intent: QueryIntent
    facts: list[LlamaFactSnapshot] = Field(default_factory=list, max_length=40)
    missing_fields: list[str] = Field(default_factory=list, max_length=20)
    ambiguities: list[str] = Field(default_factory=list, max_length=20)
    heuristic_route: LlamaHeuristicRouteContext
    requires_clarification: bool = False
    requires_human_review: bool = False
    retrieval_evidence_included: Literal[False] = False
    normative_applicability_results_included: Literal[False] = False
    rbs_determinative_result_included: Literal[False] = False
    cbr_operational_result_included: Literal[False] = False
    jurisprudence_ratio_included: Literal[False] = False
    legal_decision_included: Literal[False] = False
    requires_later_validation: Literal[True] = True
    can_control_legal_decision: Literal[False] = False


class JurisprudentialRatioContext(BaseModel):
    """Contexto fuente para que F.3 formule H2 desde la Justificación oficial."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    phase: Literal[LlamaHybridContextPhase.JURISPRUDENTIAL_RATIO] = (
        LlamaHybridContextPhase.JURISPRUDENTIAL_RATIO
    )
    document_id: str = Field(min_length=3, max_length=200)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    criterion_type: JurisprudenceCriterionType
    facts_text: str | None = Field(default=None, max_length=12000)
    legal_criterion_text: str | None = Field(default=None, max_length=12000)
    justification_text: str = Field(min_length=1, max_length=24000)
    facts_source_pages: list[int] = Field(default_factory=list, max_length=100)
    legal_criterion_source_pages: list[int] = Field(default_factory=list, max_length=100)
    justification_source_pages: list[int] = Field(min_length=1, max_length=100)
    ratio_source_section: Literal[JurisprudenceRatioSourceSection.JUSTIFICATION] = (
        JurisprudenceRatioSourceSection.JUSTIFICATION
    )
    candidate_normative_refs: list[str] = Field(default_factory=list, max_length=100)
    material_relation_types: list[str] = Field(default_factory=list, max_length=20)
    binding_character_mandatory: bool = False
    binding_from: date | None = None
    e5_authorized_for_evidence: bool = False
    e5_requires_human_review: bool = False
    source_scope: Literal["session"] = "session"
    user_attached: Literal[True] = True
    thematic_similarity_used: Literal[False] = False
    e6_application_result_included: Literal[False] = False
    legal_decision_included: Literal[False] = False
    ratio_is_not_yet_authoritative: Literal[True] = True
    requires_later_validation: Literal[True] = True
    can_control_legal_decision: Literal[False] = False

    @model_validator(mode="after")
    def enforce_ratio_source_boundary(self) -> JurisprudentialRatioContext:
        if not self.justification_text.strip():
            raise ValueError("F.2 no puede construir H2 sin Justificación oficial.")
        if not self.justification_source_pages:
            raise ValueError("F.2 exige trazabilidad de páginas para la Justificación.")
        for values in (
            self.facts_source_pages,
            self.legal_criterion_source_pages,
            self.justification_source_pages,
            self.candidate_normative_refs,
            self.material_relation_types,
        ):
            if len(values) != len(set(values)):
                raise ValueError("F.2 no admite referencias jurisprudenciales duplicadas.")
        return self


class PostDeterministicHybridReviewContext(BaseModel):
    """Contexto de contraste posterior para F.6/F.7 y explicación madura.

    Aquí sí pueden viajar los resultados deterministas ya calculados. El objeto
    sigue siendo sólo contexto y no puede redecidir la conclusión.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    phase: Literal[LlamaHybridContextPhase.POST_DETERMINISTIC_REVIEW] = (
        LlamaHybridContextPhase.POST_DETERMINISTIC_REVIEW
    )
    question: str = Field(min_length=1, max_length=4000)
    applicable_normative_refs: list[str] = Field(default_factory=list, max_length=100)
    rule_conclusions: list[str] = Field(default_factory=list, max_length=100)
    rbs_conclusion: str | None = Field(default=None, max_length=4000)
    rbs_requires_review: bool = False
    cbr_case_refs: list[str] = Field(default_factory=list, max_length=20)
    cbr_requires_review: bool = False
    hybrid_relation: str | None = Field(default=None, max_length=100)
    hybrid_conclusion: str | None = Field(default=None, max_length=4000)
    hybrid_controlling_source: str | None = Field(default=None, max_length=100)
    hybrid_reasons: list[str] = Field(default_factory=list, max_length=20)
    heuristic_signals: list[str] = Field(default_factory=list, max_length=100)
    heuristic_priorities: list[str] = Field(default_factory=list, max_length=100)
    jurisprudence_applicable_document_ids: list[str] = Field(
        default_factory=list, max_length=20
    )
    jurisprudence_binding_evidence_refs: list[str] = Field(
        default_factory=list, max_length=100
    )
    jurisprudence_requires_review: bool = False
    source_results_already_computed: Literal[True] = True
    legal_decision_included: Literal[False] = False
    may_explain_or_verify_only: Literal[True] = True
    can_change_deterministic_result: Literal[False] = False
    can_control_legal_decision: Literal[False] = False

    @model_validator(mode="after")
    def validate_unique_refs(self) -> PostDeterministicHybridReviewContext:
        for values in (
            self.applicable_normative_refs,
            self.rule_conclusions,
            self.cbr_case_refs,
            self.hybrid_reasons,
            self.heuristic_signals,
            self.heuristic_priorities,
            self.jurisprudence_applicable_document_ids,
            self.jurisprudence_binding_evidence_refs,
        ):
            if len(values) != len(set(values)):
                raise ValueError("F.2 no admite referencias duplicadas en el contexto híbrido.")
        return self
