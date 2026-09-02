from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class NormativeBindingPrecision(StrEnum):
    SOURCE = "source"
    ARTICLE = "article"
    MIXED = "mixed"


class PrimaryRBSNormativeBinding(BaseModel):
    """Vínculo B.6 entre una relación RBS primaria y el corpus normativo interno."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    binding_id: str = Field(pattern=r"^B6-BIND-[0-9]{3}$")
    relation_id: str = Field(pattern=r"^B5-REL-[0-9]{3}$")
    rule_family_ids: list[str] = Field(min_length=1, max_length=17)
    normative_source_ids: list[str] = Field(min_length=1, max_length=12)
    exact_normative_refs: list[str] = Field(default_factory=list, max_length=50)
    precision: NormativeBindingPrecision
    requires_current_corpus_validation: bool = True
    creates_executable_rule: bool = False
    can_control_legal_decision: bool = False

    @field_validator(
        "rule_family_ids",
        "normative_source_ids",
        "exact_normative_refs",
    )
    @classmethod
    def unique_values(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("B.6 no admite referencias duplicadas.")
        return values

    @field_validator("exact_normative_refs")
    @classmethod
    def validate_exact_refs(cls, refs: list[str]) -> list[str]:
        for ref in refs:
            if ":" not in ref:
                raise ValueError("La referencia normativa exacta debe usar source:locator.")
            source_id, locator = ref.split(":", 1)
            if not source_id or not locator:
                raise ValueError("Referencia normativa exacta incompleta.")
        return refs

    @model_validator(mode="after")
    def validate_boundary(self) -> PrimaryRBSNormativeBinding:
        if self.precision == NormativeBindingPrecision.SOURCE and self.exact_normative_refs:
            raise ValueError("precision=source no admite referencias exactas.")
        if self.precision == NormativeBindingPrecision.ARTICLE and not self.exact_normative_refs:
            raise ValueError("precision=article requiere referencias exactas.")
        if self.precision == NormativeBindingPrecision.MIXED and not self.exact_normative_refs:
            raise ValueError("precision=mixed requiere al menos una referencia exacta.")
        if not self.requires_current_corpus_validation:
            raise ValueError("La validación de vigencia corresponde a B.8.")
        if self.creates_executable_rule:
            raise ValueError("B.6 vincula evidencia; no crea reglas ejecutables.")
        if self.can_control_legal_decision:
            raise ValueError("B.6 no puede controlar una decisión jurídica.")
        return self


class PrimaryRBSNormativeBindingMap(BaseModel):
    """Mapa B.6 de referencias normativas para las relaciones consolidadas B.5."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    purpose: str = Field(min_length=20, max_length=1000)
    bindings: list[PrimaryRBSNormativeBinding] = Field(min_length=1, max_length=200)
    total_bindings: int = Field(ge=1)
    modifies_production_rules: bool = False

    @model_validator(mode="after")
    def validate_map(self) -> PrimaryRBSNormativeBindingMap:
        if self.total_bindings != len(self.bindings):
            raise ValueError("total_bindings no coincide con bindings.")
        binding_ids = [binding.binding_id for binding in self.bindings]
        relation_ids = [binding.relation_id for binding in self.bindings]
        if len(binding_ids) != len(set(binding_ids)):
            raise ValueError("binding_id duplicado en B.6.")
        if len(relation_ids) != len(set(relation_ids)):
            raise ValueError("Cada relación B.5 debe tener un solo vínculo B.6.")
        if self.modifies_production_rules:
            raise ValueError("B.6 no modifica las reglas productivas actuales.")
        return self
