from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PrimaryRelationSource(StrEnum):
    PRODECON = "prodecon"
    UNAM = "unam"


class ExtractedPrimaryRBSRelation(BaseModel):
    """Relación conceptual extraída de una fuente primaria; no es una regla decisoria."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    relation_id: str = Field(pattern=r"^[PU]-REL-[0-9]{3}$")
    source: PrimaryRelationSource
    source_entry_id: str = Field(pattern=r"^(PRODECON-[0-9]{2}|UNAM-[IVX]+)$")
    subject_concept: str = Field(min_length=2, max_length=120)
    predicate: str = Field(min_length=2, max_length=120)
    object_concept: str = Field(min_length=2, max_length=160)
    rbs_families: list[str] = Field(min_length=1, max_length=10)
    candidate_normative_sources: list[str] = Field(min_length=1, max_length=12)
    canonical_relation_ids: list[str] = Field(default_factory=list, max_length=12)
    requires_normative_validation: bool = True
    can_control_legal_decision: bool = False

    @field_validator(
        "rbs_families",
        "candidate_normative_sources",
        "canonical_relation_ids",
    )
    @classmethod
    def unique_values(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("Las relaciones extraídas no admiten valores duplicados.")
        return values

    @model_validator(mode="after")
    def validate_source_boundary(self) -> ExtractedPrimaryRBSRelation:
        expected_prefix = (
            "PRODECON-" if self.source == PrimaryRelationSource.PRODECON else "UNAM-"
        )
        relation_prefix = "P-REL-" if self.source == PrimaryRelationSource.PRODECON else "U-REL-"
        if not self.source_entry_id.startswith(expected_prefix):
            raise ValueError("source_entry_id no corresponde a la fuente declarada.")
        if not self.relation_id.startswith(relation_prefix):
            raise ValueError("relation_id no corresponde a la fuente declarada.")
        if not self.requires_normative_validation:
            raise ValueError("Toda relación primaria requiere validación normativa.")
        if self.can_control_legal_decision:
            raise ValueError("Una relación primaria no puede controlar la decisión jurídica.")
        return self


class PrimaryRBSRelationExtraction(BaseModel):
    """Extracción B.3/B.4 previa a deduplicación B.5."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    source: PrimaryRelationSource
    purpose: str = Field(min_length=20, max_length=1000)
    relations: list[ExtractedPrimaryRBSRelation] = Field(min_length=1, max_length=500)
    source_entry_count: int = Field(ge=1)
    deduplicated: bool = False

    @model_validator(mode="after")
    def validate_extraction(self) -> PrimaryRBSRelationExtraction:
        if any(relation.source != self.source for relation in self.relations):
            raise ValueError("La extracción mezcla fuentes primarias.")
        ids = [relation.relation_id for relation in self.relations]
        if len(ids) != len(set(ids)):
            raise ValueError("relation_id duplicado en extracción primaria.")
        if self.deduplicated:
            raise ValueError("La deduplicación corresponde a B.5.")
        return self
