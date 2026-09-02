from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PrimaryRBSDecisionRole(StrEnum):
    ORIENTATION = "orientation"
    DETERMINATION_CANDIDATE = "determination_candidate"


class PrimaryRBSDecisionBoundary(BaseModel):
    """Clasificación B.7 de una relación RBS respecto de orientación y determinación."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    boundary_id: str = Field(pattern=r"^B7-BOUND-[0-9]{3}$")
    relation_id: str = Field(pattern=r"^B5-REL-[0-9]{3}$")
    binding_id: str = Field(pattern=r"^B6-BIND-[0-9]{3}$")
    role: PrimaryRBSDecisionRole
    orientation_sources: list[str] = Field(min_length=1, max_length=19)
    normative_source_ids: list[str] = Field(min_length=1, max_length=12)
    exact_normative_refs: list[str] = Field(default_factory=list, max_length=50)
    requires_normative_validation: bool = True
    requires_rule_conditions: bool = True
    executable_determination_enabled: bool = False
    primary_sources_can_control_outcome: bool = False

    @field_validator(
        "orientation_sources",
        "normative_source_ids",
        "exact_normative_refs",
    )
    @classmethod
    def unique_values(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("B.7 no admite valores duplicados.")
        return values

    @model_validator(mode="after")
    def validate_boundary(self) -> PrimaryRBSDecisionBoundary:
        if not self.requires_normative_validation:
            raise ValueError("B.7 no puede omitir la validación normativa.")
        if not self.requires_rule_conditions:
            raise ValueError("Toda determinación requiere condiciones fácticas/reglas.")
        if self.executable_determination_enabled:
            raise ValueError("B.7 no habilita todavía determinaciones ejecutables.")
        if self.primary_sources_can_control_outcome:
            raise ValueError("PRODECON/UNAM no pueden controlar el resultado jurídico.")
        if (
            self.role == PrimaryRBSDecisionRole.DETERMINATION_CANDIDATE
            and not self.exact_normative_refs
        ):
            raise ValueError(
                "Una relación candidata a determinación requiere referencia normativa exacta."
            )
        return self


class PrimaryRBSDecisionBoundaryMap(BaseModel):
    """Mapa B.7 que separa la navegación heurística de la determinación jurídica."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    purpose: str = Field(min_length=20, max_length=1000)
    boundaries: list[PrimaryRBSDecisionBoundary] = Field(min_length=1, max_length=200)
    total_boundaries: int = Field(ge=1)
    orientation_is_non_controlling: bool = True
    determination_requires_internal_normative_evidence: bool = True
    modifies_production_rules: bool = False

    @model_validator(mode="after")
    def validate_map(self) -> PrimaryRBSDecisionBoundaryMap:
        if self.total_boundaries != len(self.boundaries):
            raise ValueError("total_boundaries no coincide con boundaries.")
        ids = [boundary.boundary_id for boundary in self.boundaries]
        relation_ids = [boundary.relation_id for boundary in self.boundaries]
        binding_ids = [boundary.binding_id for boundary in self.boundaries]
        if len(ids) != len(set(ids)):
            raise ValueError("boundary_id duplicado en B.7.")
        if len(relation_ids) != len(set(relation_ids)):
            raise ValueError("Cada relación B.5 debe clasificarse una sola vez.")
        if len(binding_ids) != len(set(binding_ids)):
            raise ValueError("Cada binding B.6 debe clasificarse una sola vez.")
        if not self.orientation_is_non_controlling:
            raise ValueError("La orientación primaria debe ser no controlante.")
        if not self.determination_requires_internal_normative_evidence:
            raise ValueError("La determinación exige evidencia normativa interna.")
        if self.modifies_production_rules:
            raise ValueError("B.7 no modifica reglas productivas.")
        return self
