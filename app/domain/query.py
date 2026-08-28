from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


class QueryIntent(StrEnum):
    UNDERSTAND_TAX_SYSTEM = "understand_tax_system"
    IDENTIFY_OBLIGATIONS = "identify_obligations"
    KNOW_RIGHTS = "know_rights"
    CALCULATE_ISR = "calculate_isr"
    CALCULATE_IVA = "calculate_iva"
    ANALYZE_AUTHORITY_ACT = "analyze_authority_act"
    REVIEW_DEBT_NONCOMPLIANCE = "review_debt_noncompliance"
    DEFENSE_OPTIONS = "defense_options"
    INTERPRET_PROVISION = "interpret_provision"
    RELATED_JURISPRUDENCE = "related_jurisprudence"
    SIMILAR_CASES = "similar_cases"
    LEARN_TAX_LAW = "learn_tax_law"
    UNKNOWN = "unknown"


class FactOrigin(StrEnum):
    EXPLICIT = "explicit"
    INFERRED = "inferred"


class ExtractedFact(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=1000)
    origin: FactOrigin = FactOrigin.EXPLICIT

    @field_validator("name", "value")
    @classmethod
    def strip_text(cls, value: str) -> str:
        clean = " ".join(value.split())
        if not clean:
            raise ValueError("El valor no puede quedar vacío.")
        return clean


class QueryEntity(BaseModel):
    entity_type: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=500)

    @field_validator("entity_type", "value")
    @classmethod
    def strip_text(cls, value: str) -> str:
        clean = " ".join(value.split())
        if not clean:
            raise ValueError("La entidad no puede quedar vacía.")
        return clean


class MissingField(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=500)


class QueryAnalysisDraft(BaseModel):
    primary_intent: QueryIntent
    secondary_intents: list[QueryIntent] = Field(default_factory=list, max_length=8)
    facts: list[ExtractedFact] = Field(default_factory=list, max_length=40)
    entities: list[QueryEntity] = Field(default_factory=list, max_length=40)
    missing_fields: list[MissingField] = Field(default_factory=list, max_length=20)
    ambiguities: list[str] = Field(default_factory=list, max_length=20)
    jurisprudence_requested: bool = False
    requires_clarification: bool = False
    requires_human_review: bool = False

    @field_validator("ambiguities")
    @classmethod
    def normalize_ambiguities(cls, values: list[str]) -> list[str]:
        return [" ".join(value.split()) for value in values if value.strip()]

    @model_validator(mode="after")
    def remove_duplicate_secondary_intent(self) -> QueryAnalysisDraft:
        self.secondary_intents = [
            intent for intent in dict.fromkeys(self.secondary_intents)
            if intent != self.primary_intent
        ]
        return self


class QueryAnalysis(BaseModel):
    original_query: str = Field(min_length=1, max_length=4000)
    normalized_query: str = Field(min_length=1, max_length=4000)
    primary_intent: QueryIntent
    secondary_intents: list[QueryIntent] = Field(default_factory=list)
    facts: list[ExtractedFact] = Field(default_factory=list)
    entities: list[QueryEntity] = Field(default_factory=list)
    missing_fields: list[MissingField] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    jurisprudence_requested: bool = False
    requires_clarification: bool = False
    requires_human_review: bool = False
