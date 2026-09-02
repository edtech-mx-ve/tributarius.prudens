from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RBSFamilyCategory(StrEnum):
    SUBJECT = "subject"
    TAX_STRUCTURE = "tax_structure"
    COMPLIANCE = "compliance"
    AUTHORITY = "authority"
    CONSEQUENCE = "consequence"
    PROCEDURE = "procedure"
    INTERPRETATION = "interpretation"
    TEMPORALITY = "temporality"


class PrimaryRBSFamily(BaseModel):
    """Familia general B.2; clasifica reglas futuras sin crear una determinación."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    family_id: str = Field(pattern=r"^R-[A-Z]{3}$")
    rule_prefix: str = Field(pattern=r"^R-[A-Z]{3}-$")
    name: str = Field(min_length=3, max_length=120)
    category: RBSFamilyCategory
    purpose: str = Field(min_length=20, max_length=800)
    legal_dimensions: list[str] = Field(min_length=1, max_length=30)
    primary_entry_ids: list[str] = Field(default_factory=list, max_length=19)
    enabled_for_design: bool = True
    creates_rules: bool = False

    @field_validator("legal_dimensions", "primary_entry_ids")
    @classmethod
    def unique_values(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("B.2 no admite valores duplicados dentro de una familia.")
        return values

    @model_validator(mode="after")
    def validate_design_boundary(self) -> PrimaryRBSFamily:
        if self.rule_prefix != f"{self.family_id}-":
            raise ValueError("rule_prefix debe derivarse exactamente de family_id.")
        if self.creates_rules:
            raise ValueError("B.2 diseña familias; todavía no crea reglas RBS.")
        return self


class PrimaryRBSFamilyRegistry(BaseModel):
    """Registro cerrado de familias generales para RBS Primario 1.0."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    purpose: str = Field(min_length=20, max_length=1000)
    families: list[PrimaryRBSFamily] = Field(min_length=1, max_length=100)
    total_families: int = Field(ge=1)
    modifies_current_rules: bool = False

    @model_validator(mode="after")
    def validate_registry(self) -> PrimaryRBSFamilyRegistry:
        if self.total_families != len(self.families):
            raise ValueError("total_families no coincide con el registro B.2.")
        family_ids = [family.family_id for family in self.families]
        prefixes = [family.rule_prefix for family in self.families]
        if len(family_ids) != len(set(family_ids)):
            raise ValueError("family_id duplicado en B.2.")
        if len(prefixes) != len(set(prefixes)):
            raise ValueError("rule_prefix duplicado en B.2.")
        if self.modifies_current_rules:
            raise ValueError("B.2 no puede modificar reglas RBS actuales.")
        return self
