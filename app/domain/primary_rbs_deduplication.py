from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DeduplicatedPrimaryRBSRelation(BaseModel):
    """Relación consolidada PRODECON/UNAM previa a validación normativa B.6-B.8."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    canonical_id: str = Field(pattern=r"^B5-REL-[0-9]{3}$")
    label: str = Field(min_length=3, max_length=180)
    description: str = Field(min_length=20, max_length=900)
    source_relation_ids: list[str] = Field(min_length=1, max_length=20)
    primary_entry_ids: list[str] = Field(min_length=1, max_length=19)
    rbs_families: list[str] = Field(min_length=1, max_length=17)
    candidate_normative_sources: list[str] = Field(min_length=1, max_length=12)
    legal_relation_ids: list[str] = Field(default_factory=list, max_length=12)
    requires_normative_validation: bool = True
    can_control_legal_decision: bool = False

    @field_validator(
        "source_relation_ids",
        "primary_entry_ids",
        "rbs_families",
        "candidate_normative_sources",
        "legal_relation_ids",
    )
    @classmethod
    def unique_values(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("B.5 no admite valores duplicados dentro de una relación.")
        return values

    @model_validator(mode="after")
    def validate_boundary(self) -> DeduplicatedPrimaryRBSRelation:
        if not self.requires_normative_validation:
            raise ValueError("B.5 siempre requiere validación normativa posterior.")
        if self.can_control_legal_decision:
            raise ValueError("B.5 no puede controlar una decisión jurídica.")
        return self


class PrimaryRBSDeduplicationMap(BaseModel):
    """Mapa B.5 que relaciona y deduplica ambas fuentes primarias."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    purpose: str = Field(min_length=20, max_length=1000)
    source_relation_count: int = Field(ge=1)
    deduplicated_relation_count: int = Field(ge=1)
    relations: list[DeduplicatedPrimaryRBSRelation] = Field(min_length=1, max_length=200)
    preserves_source_provenance: bool = True

    @model_validator(mode="after")
    def validate_counts(self) -> PrimaryRBSDeduplicationMap:
        if self.deduplicated_relation_count != len(self.relations):
            raise ValueError("deduplicated_relation_count no coincide con B.5.")
        ids = [relation.canonical_id for relation in self.relations]
        if len(ids) != len(set(ids)):
            raise ValueError("canonical_id duplicado en B.5.")
        if not self.preserves_source_provenance:
            raise ValueError("B.5 debe preservar la procedencia de ambas fuentes.")
        return self
