from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.hybrid_coordination import HybridReasoningRelation


class RBSH1ContrastState(StrEnum):
    """Estado operacional del contraste determinista entre RBS e H1."""

    NOT_APPLICABLE = "not_applicable"
    CONTRASTED = "contrasted"
    INCONCLUSIVE = "inconclusive"


class RBSH1NormativeAlignment(StrEnum):
    """Cobertura de las referencias normativas candidatas de H1 por el RBS."""

    NOT_PROPOSED = "not_proposed"
    ALIGNED = "aligned"
    PARTIAL = "partial"
    DISJOINT = "disjoint"


class RBSH1ContrastResult(BaseModel):
    """Contraste F.4 entre la hipótesis H1 y el resultado determinativo del RBS.

    La relación describe cómo el RBS trata la hipótesis. Nunca permite que H1
    modifique reglas, conclusiones, derivaciones ni la fuente controladora.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    state: RBSH1ContrastState
    hypothesis_id: str | None = Field(default=None, pattern=r"^H1-[a-f0-9]{16}$")
    relation: HybridReasoningRelation | None = None
    h1_proposition: str | None = Field(default=None, max_length=4000)
    rbs_conclusions: list[str] = Field(default_factory=list, max_length=100)
    matched_rule_ids: list[str] = Field(default_factory=list, max_length=5000)
    matched_conclusion_codes: list[str] = Field(default_factory=list, max_length=5000)
    h1_candidate_normative_refs: list[str] = Field(default_factory=list, max_length=100)
    rbs_normative_refs: list[str] = Field(default_factory=list, max_length=5000)
    shared_normative_refs: list[str] = Field(default_factory=list, max_length=100)
    unsupported_h1_normative_refs: list[str] = Field(default_factory=list, max_length=100)
    normative_alignment: RBSH1NormativeAlignment = RBSH1NormativeAlignment.NOT_PROPOSED
    h1_fact_names: list[str] = Field(default_factory=list, max_length=40)
    rbs_supporting_fact_names: list[str] = Field(default_factory=list, max_length=5000)
    shared_fact_names: list[str] = Field(default_factory=list, max_length=40)
    explicit_exception_rule_ids: list[str] = Field(default_factory=list, max_length=5000)
    exact_text_confirmation: bool | None = None
    explicit_negation_conflict: bool | None = None
    rbs_requires_human_review: bool = False
    controlling_source: Literal["rbs"] | None = None
    rbs_result_used: Literal[True] = True
    rbs_reexecuted: Literal[False] = False
    semantic_equivalence_inferred: Literal[False] = False
    h1_normative_refs_treated_as_candidates: Literal[True] = True
    rbs_authority_preserved: Literal[True] = True
    deterministic_result_preserved: Literal[True] = True
    hypothesis_changes_rbs_result: Literal[False] = False
    can_control_legal_decision: Literal[False] = False
    reasons: list[str] = Field(default_factory=list, max_length=30)
    requires_human_review: bool = False
    trace: list[str] = Field(default_factory=list, max_length=40)
