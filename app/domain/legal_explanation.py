from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.explanation_mode import ExplanationMode


class LegalExplanationInvariant(BaseModel):
    """Contenido jurídico que ningún perfil de explicación puede alterar."""

    applicable_normative_refs: list[str] = Field(default_factory=list, max_length=100)
    rule_conclusions: list[str] = Field(default_factory=list, max_length=100)
    calculations: list[str] = Field(default_factory=list, max_length=50)
    similar_cases: list[str] = Field(default_factory=list, max_length=20)
    jurisprudential_criteria: list[str] = Field(default_factory=list, max_length=20)
    hybrid_relation: str | None = Field(default=None, max_length=100)
    hybrid_conclusion: str | None = Field(default=None, max_length=4000)
    hybrid_controlling_source: str | None = Field(default=None, max_length=100)
    hybrid_reasons: list[str] = Field(default_factory=list, max_length=20)
    heuristic_signals: list[str] = Field(default_factory=list, max_length=100)
    heuristic_priorities: list[str] = Field(default_factory=list, max_length=100)
    heuristic_requires_review: bool = False
    requires_human_review: bool = False


class LegalExplanationProfile(BaseModel):
    """Contrato exclusivamente comunicativo de un modo de explicación."""

    mode: ExplanationMode
    audience_label: str = Field(min_length=1, max_length=100)
    communication_goal: str = Field(min_length=1, max_length=500)
    section_order: list[str] = Field(min_length=1, max_length=10)
    style_instructions: list[str] = Field(min_length=1, max_length=10)


class MatureLegalExplanationContext(BaseModel):
    """Frontera madura: un resultado jurídico, distintas presentaciones."""

    invariant: LegalExplanationInvariant
    profile: LegalExplanationProfile
