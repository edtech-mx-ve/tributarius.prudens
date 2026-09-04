from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.cbr import CaseField, CaseStatus, CBRReuseDecision


class CBRH1ContrastState(StrEnum):
    """Estado operacional del contraste analógico CBR frente a H1."""

    NOT_APPLICABLE = "not_applicable"
    CONTRASTED = "contrasted"
    INCONCLUSIVE = "inconclusive"


class CBRAnalogicalEffect(StrEnum):
    """Efecto experiencial del caso análogo sobre la hipótesis H1.

    Estos estados no expresan autoridad normativa ni una votación frente al
    RBS. Describen únicamente el valor analógico controlado del CBR.
    """

    SUPPORT = "support"
    LIMIT = "limit"
    DISTINGUISH = "distinguish"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class CBRCaseH1Contrast(BaseModel):
    """Contraste individual entre un caso CBR recuperado y H1."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    rank: int = Field(ge=1)
    similarity: float = Field(ge=0.0, le=1.0)
    status: CaseStatus
    reuse_decision: CBRReuseDecision | None = None
    effect: CBRAnalogicalEffect
    normative_refs: list[str] = Field(default_factory=list, max_length=100)
    shared_h1_normative_refs: list[str] = Field(default_factory=list, max_length=100)
    material_difference_fields: list[CaseField] = Field(default_factory=list, max_length=7)
    critical_conflict_fields: list[CaseField] = Field(default_factory=list, max_length=3)
    historical_context: bool = False
    exact_text_support: bool = False
    explicit_negation_adversity: bool = False
    requires_human_review: bool = False
    reasons: list[str] = Field(default_factory=list, max_length=20)


class CBRH1ContrastResult(BaseModel):
    """Resultado F.5 del contraste experiencial entre CBR y H1.

    El resultado selecciona el caso reutilizable mejor rankeado; no suma votos
    entre casos y nunca transforma la experiencia CBR en norma, jurisprudencia
    o fuente controladora de la decisión jurídica.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    state: CBRH1ContrastState
    hypothesis_id: str | None = Field(default=None, pattern=r"^H1-[a-f0-9]{16}$")
    effect: CBRAnalogicalEffect | None = None
    h1_proposition: str | None = Field(default=None, max_length=4000)
    h1_candidate_normative_refs: list[str] = Field(default_factory=list, max_length=100)
    considered_case_ids: list[str] = Field(default_factory=list, max_length=20)
    eligible_case_ids: list[str] = Field(default_factory=list, max_length=20)
    review_required_case_ids: list[str] = Field(default_factory=list, max_length=20)
    rejected_case_ids: list[str] = Field(default_factory=list, max_length=20)
    selected_case_id: str | None = Field(default=None, max_length=100)
    selected_case_similarity: float | None = Field(default=None, ge=0.0, le=1.0)
    cbr_normative_refs: list[str] = Field(default_factory=list, max_length=500)
    shared_h1_normative_refs: list[str] = Field(default_factory=list, max_length=100)
    material_difference_fields: list[CaseField] = Field(default_factory=list, max_length=7)
    critical_conflict_fields: list[CaseField] = Field(default_factory=list, max_length=3)
    temporal_distinction_detected: bool = False
    exact_text_support: bool | None = None
    explicit_negation_adversity: bool | None = None
    case_contrasts: list[CBRCaseH1Contrast] = Field(default_factory=list, max_length=20)
    retrieval_threshold: float = Field(ge=0.0, le=1.0)
    reuse_threshold: float = Field(ge=0.0, le=1.0)
    critical_fields: list[CaseField] = Field(default_factory=list, max_length=3)
    aggregation_method: Literal["best_ranked_reusable_case_not_vote"] = (
        "best_ranked_reusable_case_not_vote"
    )
    cbr_result_used: Literal[True] = True
    cbr_reexecuted: Literal[False] = False
    existing_cbr_retrieval_gate_preserved: Literal[True] = True
    existing_reuse_assessment_preserved: Literal[True] = True
    primary_cbr_profiles_promoted_to_operational_cases: Literal[False] = False
    family_taxonomy_similarity_recomputed: Literal[False] = False
    h1_normative_refs_treated_as_candidates: Literal[True] = True
    semantic_equivalence_inferred: Literal[False] = False
    cbr_is_experiential_support: Literal[True] = True
    cbr_is_normative_authority: Literal[False] = False
    cbr_is_jurisprudence: Literal[False] = False
    cbr_votes_against_rbs: Literal[False] = False
    rbs_result_used: Literal[False] = False
    may_assist_later_h2_fact_comparison: Literal[True] = True
    hypothesis_changes_cbr_result: Literal[False] = False
    can_control_legal_decision: Literal[False] = False
    reasons: list[str] = Field(default_factory=list, max_length=30)
    requires_human_review: bool = False
    trace: list[str] = Field(default_factory=list, max_length=50)
