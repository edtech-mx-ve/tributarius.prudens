from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class RuleOperator(StrEnum):
    EQ = "eq"
    NE = "ne"
    IN = "in"
    NOT_IN = "not_in"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    EXISTS = "exists"


class RuleCondition(BaseModel):
    fact: str = Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    operator: RuleOperator
    value: Any = None

    @model_validator(mode="after")
    def validate_value(self) -> RuleCondition:
        if self.operator in {RuleOperator.IN, RuleOperator.NOT_IN}:
            if not isinstance(self.value, list) or not self.value:
                raise ValueError("in/not_in requiere una lista no vacía.")
        if self.operator == RuleOperator.EXISTS and not isinstance(self.value, bool):
            raise ValueError("exists requiere un booleano.")
        return self


class RuleDefinition(BaseModel):
    rule_id: str = Field(min_length=3, max_length=100, pattern=r"^[A-Z][A-Z0-9_]+$")
    version: str = Field(min_length=1, max_length=50)
    description: str = Field(min_length=1, max_length=500)
    priority: int = Field(default=100, ge=0, le=10_000)
    enabled: bool = True
    conditions: list[RuleCondition] = Field(min_length=1, max_length=50)
    conclusion_code: str = Field(
        min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$"
    )
    conclusion: str = Field(min_length=1, max_length=1000)
    normative_refs: list[str] = Field(default_factory=list, max_length=50)
    source_refs: list[str] = Field(default_factory=list, max_length=50)
    requires_human_review: bool = False

    @field_validator("normative_refs", "source_refs")
    @classmethod
    def validate_refs(cls, refs: list[str]) -> list[str]:
        cleaned = [ref.strip() for ref in refs]
        if any(not ref or len(ref) > 300 for ref in cleaned):
            raise ValueError("Referencias inválidas.")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("Las referencias no pueden repetirse.")
        return cleaned


class RuleSet(BaseModel):
    schema_version: str = Field(pattern=r"^1\.\d+$")
    rules: list[RuleDefinition] = Field(min_length=1, max_length=5000)

    @model_validator(mode="after")
    def validate_unique_rule_versions(self) -> RuleSet:
        keys = [(rule.rule_id, rule.version) for rule in self.rules]
        if len(keys) != len(set(keys)):
            raise ValueError("rule_id/version duplicado.")
        return self


class ConditionTrace(BaseModel):
    fact: str
    operator: RuleOperator
    expected: Any = None
    actual: Any = None
    matched: bool


class RuleTrace(BaseModel):
    rule_id: str
    version: str
    priority: int
    matched: bool
    skipped_reason: str | None = None
    conditions: list[ConditionTrace] = Field(default_factory=list)


class RuleConclusion(BaseModel):
    rule_id: str
    version: str
    conclusion_code: str
    conclusion: str
    normative_refs: list[str]
    source_refs: list[str]
    requires_human_review: bool


class RuleEvaluationResult(BaseModel):
    matched_rules: list[RuleConclusion]
    traces: list[RuleTrace]
    requires_human_review: bool
