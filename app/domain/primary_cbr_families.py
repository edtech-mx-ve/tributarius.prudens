from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.primary_cbr_corpus_validation import PrimaryCBRCorpusValidationOutcome
from app.domain.primary_legal_knowledge import PrimaryManual


class PrimaryCBRFamilyDefinition(BaseModel):
    """Familia CBR primaria formalizada en C.8 a partir de A.6/C.1."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    family_id: str = Field(pattern=r"^CBR-[A-Z]+$")
    label: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=20, max_length=700)
    source_concept_ids: list[str] = Field(min_length=1, max_length=12)
    primary_anchor_concept_ids: list[str] = Field(default_factory=list, max_length=12)
    present_in_c1_inventory: bool = True
    derived_from_a6: bool = True
    retrieval_partition_only: bool = True
    normative_authority: bool = False
    can_control_legal_decision: bool = False

    @field_validator("source_concept_ids", "primary_anchor_concept_ids")
    @classmethod
    def unique_concepts(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("C.8 no admite conceptos duplicados dentro de una familia.")
        return values

    @model_validator(mode="after")
    def validate_boundary(self) -> PrimaryCBRFamilyDefinition:
        if not self.present_in_c1_inventory or not self.derived_from_a6:
            raise ValueError("C.8 sólo formaliza familias ya referenciadas por C.1/A.6.")
        if not self.retrieval_partition_only:
            raise ValueError("La familia CBR C.8 sólo clasifica y particiona recuperación.")
        if self.normative_authority or self.can_control_legal_decision:
            raise ValueError("Una familia CBR no puede convertirse en autoridad normativa.")
        if not set(self.primary_anchor_concept_ids) <= set(self.source_concept_ids):
            raise ValueError("Los conceptos ancla deben pertenecer a la familia A.6.")
        return self


class PrimaryCBRFamilyAssignment(BaseModel):
    """Asignación C.8 de una situación primaria a una familia principal y facetas."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    situation_id: str = Field(pattern=r"^(P|U)-CBR-SIT-[0-9]{3}$")
    source: PrimaryManual
    source_entry_id: str = Field(pattern=r"^(PRODECON-\d{2}|UNAM-[IVX]+)$")
    historical_regime_context: bool
    primary_problem_id: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]*$")
    primary_institution_id: str | None = Field(
        default=None, pattern=r"^[a-z][a-z0-9_]*$"
    )
    family_basis_concept_ids: list[str] = Field(min_length=1, max_length=12)
    primary_family_id: str = Field(pattern=r"^CBR-[A-Z]+$")
    family_ids: list[str] = Field(min_length=1, max_length=12)
    corpus_validation_outcome: PrimaryCBRCorpusValidationOutcome
    corpus_validated: bool
    temporal_validation_pending: bool = True
    facts_normalized: bool = True
    problem_institution_classified: bool = True
    normative_articles_linked: bool = True
    corpus_validation_completed: bool = True
    cbr_family_assigned: bool = True
    legal_similarity_enabled: bool = False
    operational_case_created: bool = False
    can_control_legal_decision: bool = False

    @field_validator("family_basis_concept_ids", "family_ids")
    @classmethod
    def unique_values(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("C.8 no admite conceptos o familias duplicadas.")
        return values

    @model_validator(mode="after")
    def validate_assignment(self) -> PrimaryCBRFamilyAssignment:
        if self.primary_problem_id is None and self.primary_institution_id is None:
            raise ValueError("C.8 requiere al menos un concepto primario clasificado por C.5.")
        if self.primary_family_id not in self.family_ids:
            raise ValueError("La familia principal debe pertenecer a family_ids.")
        if self.family_ids[0] != self.primary_family_id:
            raise ValueError("C.8 ordena la familia principal en la primera posición.")
        if not (
            self.temporal_validation_pending
            and self.facts_normalized
            and self.problem_institution_classified
            and self.normative_articles_linked
            and self.corpus_validation_completed
            and self.cbr_family_assigned
        ):
            raise ValueError("C.8 debe preservar C.4-C.7 y completar sólo la familia CBR.")
        if self.legal_similarity_enabled or self.operational_case_created:
            raise ValueError("C.8 no adelanta similitud C.9 ni operación C.10.")
        if self.can_control_legal_decision:
            raise ValueError("La clasificación por familia no controla Legal Decision.")
        if self.historical_regime_context and "CBR-TEMPORALIDAD" not in self.family_ids:
            raise ValueError("Los casos históricos deben conservar CBR-TEMPORALIDAD.")
        return self


class PrimaryCBRFamilyRegistry(BaseModel):
    """Registro reproducible de familias y asignaciones del CBR Primario 1.0."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    baseline_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    purpose: str = Field(min_length=20, max_length=1200)
    inventory_resource: str = Field(min_length=3, max_length=300)
    taxonomy_resource: str = Field(min_length=3, max_length=300)
    classification_resource: str = Field(min_length=3, max_length=300)
    corpus_validation_resource: str = Field(min_length=3, max_length=300)
    family_count: int = Field(ge=1, le=100)
    assigned_situation_count: int = Field(ge=1)
    primary_family_coverage_count: int = Field(ge=1, le=100)
    secondary_only_family_ids: list[str] = Field(default_factory=list, max_length=100)
    primary_family_counts: dict[str, int] = Field(min_length=1, max_length=100)
    family_membership_counts: dict[str, int] = Field(min_length=1, max_length=100)
    families: list[PrimaryCBRFamilyDefinition] = Field(min_length=1, max_length=100)
    assignments: list[PrimaryCBRFamilyAssignment] = Field(min_length=1)
    preserves_c7_validation_state: bool = True
    uses_only_c1_a6_family_ids: bool = True
    enables_legal_similarity: bool = False
    creates_operational_cases: bool = False
    modifies_existing_cbr_engine: bool = False
    can_control_legal_decision: bool = False

    @field_validator("secondary_only_family_ids")
    @classmethod
    def unique_secondary_only(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("secondary_only_family_ids contiene duplicados.")
        return values

    @model_validator(mode="after")
    def validate_registry(self) -> PrimaryCBRFamilyRegistry:
        family_ids = [item.family_id for item in self.families]
        if len(family_ids) != len(set(family_ids)):
            raise ValueError("C.8 contiene familias duplicadas.")
        situation_ids = [item.situation_id for item in self.assignments]
        if len(situation_ids) != len(set(situation_ids)):
            raise ValueError("C.8 contiene situaciones duplicadas.")
        if self.family_count != len(self.families):
            raise ValueError("family_count no coincide con el registro C.8.")
        if self.assigned_situation_count != len(self.assignments):
            raise ValueError("assigned_situation_count no coincide con C.8.")
        known = set(family_ids)
        if set(self.primary_family_counts) != known:
            raise ValueError("primary_family_counts debe cubrir exactamente las familias C.8.")
        if set(self.family_membership_counts) != known:
            raise ValueError("family_membership_counts debe cubrir exactamente las familias C.8.")
        actual_primary = {item.primary_family_id for item in self.assignments}
        if self.primary_family_coverage_count != len(actual_primary):
            raise ValueError("primary_family_coverage_count es inconsistente.")
        expected_secondary_only = [
            family_id for family_id in family_ids if family_id not in actual_primary
        ]
        if self.secondary_only_family_ids != expected_secondary_only:
            raise ValueError("secondary_only_family_ids no coincide con las asignaciones.")
        if not self.preserves_c7_validation_state or not self.uses_only_c1_a6_family_ids:
            raise ValueError("C.8 debe preservar C.7 y usar sólo familias C.1/A.6.")
        if any(
            (
                self.enables_legal_similarity,
                self.creates_operational_cases,
                self.modifies_existing_cbr_engine,
                self.can_control_legal_decision,
            )
        ):
            raise ValueError("C.8 no adelanta C.9-C.10 ni altera el CBR existente.")
        return self
