from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ExistingRBSRuleIntegration(BaseModel):
    """Puente B.9 entre una regla productiva existente y el RBS primario."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    integration_id: str = Field(pattern=r"^B9-RULE-[0-9]{3}$")
    rule_id: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    version: str = Field(min_length=1, max_length=50)
    source_file: str = Field(pattern=r"^mvp_[a-z0-9_]+\.json$")
    primary_relation_ids: list[str] = Field(min_length=1, max_length=18)
    rbs_family_ids: list[str] = Field(min_length=1, max_length=17)
    normative_refs: list[str] = Field(min_length=1, max_length=50)
    execution_mode: str = "existing_rule_engine"
    preserves_rule_definition: bool = True
    inherits_temporal_fail_closed: bool = True
    creates_duplicate_rule: bool = False

    @field_validator(
        "primary_relation_ids",
        "rbs_family_ids",
        "normative_refs",
    )
    @classmethod
    def unique_values(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("B.9 no admite valores duplicados.")
        return values

    @model_validator(mode="after")
    def validate_integration(self) -> ExistingRBSRuleIntegration:
        if self.execution_mode != "existing_rule_engine":
            raise ValueError("B.9 debe reutilizar el motor RBS existente.")
        if not self.preserves_rule_definition:
            raise ValueError("B.9 debe preservar la definición productiva original.")
        if not self.inherits_temporal_fail_closed:
            raise ValueError("B.9 debe heredar la política temporal fail-closed.")
        if self.creates_duplicate_rule:
            raise ValueError("B.9 no puede duplicar reglas productivas.")
        return self


class ExistingRBSRuleIntegrationMap(BaseModel):
    """Mapa B.9 de integración de las reglas RBS productivas actuales."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    baseline_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    purpose: str = Field(min_length=20, max_length=1200)
    production_rule_files: list[str] = Field(min_length=1, max_length=100)
    integrations: list[ExistingRBSRuleIntegration] = Field(min_length=1, max_length=5000)
    total_rules: int = Field(ge=1)
    execution_service: str = "app.services.rbr_reasoning.infer_rule_facts"
    requires_applicable_normative_refs: bool = True
    temporal_policy_fail_closed: bool = True
    modifies_production_rules: bool = False
    creates_parallel_rule_engine: bool = False

    @model_validator(mode="after")
    def validate_map(self) -> ExistingRBSRuleIntegrationMap:
        if self.total_rules != len(self.integrations):
            raise ValueError("total_rules no coincide con integrations en B.9.")
        keys = [(item.rule_id, item.version) for item in self.integrations]
        if len(keys) != len(set(keys)):
            raise ValueError("B.9 contiene rule_id/version duplicado.")
        ids = [item.integration_id for item in self.integrations]
        if len(ids) != len(set(ids)):
            raise ValueError("B.9 contiene integration_id duplicado.")
        if set(self.production_rule_files) != {
            item.source_file for item in self.integrations
        }:
            raise ValueError("B.9 debe cubrir exactamente sus archivos productivos.")
        if self.execution_service != "app.services.rbr_reasoning.infer_rule_facts":
            raise ValueError("B.9 debe reutilizar infer_rule_facts.")
        if not self.requires_applicable_normative_refs:
            raise ValueError("B.9 debe conservar el gate de evidencia normativa.")
        if not self.temporal_policy_fail_closed:
            raise ValueError("B.9 debe conservar política temporal fail-closed.")
        if self.modifies_production_rules:
            raise ValueError("B.9 no modifica las reglas productivas existentes.")
        if self.creates_parallel_rule_engine:
            raise ValueError("B.9 no crea un segundo motor de reglas.")
        return self
