from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CurrentRBSRuleKind(StrEnum):
    PROFILE = "profile"
    INCOME_CLASSIFICATION = "income_classification"
    ISR_PROFESSIONAL = "isr_professional"
    OBLIGATION = "obligation"
    RIGHT = "right"


class CurrentRBSRuleInventoryEntry(BaseModel):
    """Registro B.1 de una regla RBS existente; no redefine su contenido."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    rule_id: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    version: str
    source_file: str = Field(pattern=r"^mvp_[a-z0-9_]+\.json$")
    kind: CurrentRBSRuleKind
    conclusion_code: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    normative_refs: list[str] = Field(min_length=1, max_length=50)
    enabled: bool
    requires_human_review: bool
    integration_status: str = Field(default="existing_production_rule", frozen=True)

    @field_validator("normative_refs")
    @classmethod
    def unique_refs(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("B.1 no admite referencias normativas duplicadas.")
        return values


class CurrentRBSInventory(BaseModel):
    """Inventario exacto y auditable de las reglas RBS de producción existentes."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    baseline_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    purpose: str = Field(min_length=20, max_length=1000)
    production_rule_files: list[str] = Field(min_length=1, max_length=100)
    rules: list[CurrentRBSRuleInventoryEntry] = Field(min_length=1, max_length=5000)
    total_rules: int = Field(ge=1)
    can_modify_production_rules: bool = False

    @model_validator(mode="after")
    def validate_inventory(self) -> CurrentRBSInventory:
        if self.total_rules != len(self.rules):
            raise ValueError("total_rules no coincide con el inventario B.1.")
        keys = [(rule.rule_id, rule.version) for rule in self.rules]
        if len(keys) != len(set(keys)):
            raise ValueError("B.1 contiene rule_id/version duplicado.")
        files = set(self.production_rule_files)
        if files != {rule.source_file for rule in self.rules}:
            raise ValueError("B.1 debe cubrir exactamente los archivos RBS inventariados.")
        if self.can_modify_production_rules:
            raise ValueError("B.1 es inventario y no puede modificar reglas de producción.")
        return self
