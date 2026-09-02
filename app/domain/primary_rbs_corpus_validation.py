from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CorpusValidationStatus(StrEnum):
    STRUCTURALLY_VALIDATED = "structurally_validated"
    STRUCTURALLY_VALIDATED_WITH_TEMPORAL_BLOCK = (
        "structurally_validated_with_temporal_block"
    )


class ExactReferenceValidationStatus(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    KNOWN_EXISTING_RULE_REFERENCE = "known_existing_rule_reference"


class PrimaryRBSRelationCorpusValidation(BaseModel):
    """Resultado B.8 para una relación primaria B.5/B.7 contra el corpus interno."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    validation_id: str = Field(pattern=r"^B8-REL-[0-9]{3}$")
    relation_id: str = Field(pattern=r"^B5-REL-[0-9]{3}$")
    boundary_id: str = Field(pattern=r"^B7-BOUND-[0-9]{3}$")
    normative_source_ids: list[str] = Field(min_length=1, max_length=12)
    exact_normative_refs: list[str] = Field(default_factory=list, max_length=50)
    exact_reference_status: ExactReferenceValidationStatus
    blocked_normative_sources: list[str] = Field(default_factory=list, max_length=12)
    status: CorpusValidationStatus
    corpus_membership_validated: bool = True
    temporal_applicability_confirmed: bool = False
    requires_case_date_validation: bool = True
    determination_ready: bool = False

    @field_validator(
        "normative_source_ids",
        "exact_normative_refs",
        "blocked_normative_sources",
    )
    @classmethod
    def unique_values(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("B.8 no admite valores duplicados.")
        return values

    @model_validator(mode="after")
    def validate_fail_closed(self) -> PrimaryRBSRelationCorpusValidation:
        if not self.corpus_membership_validated:
            raise ValueError("B.8 exige pertenencia comprobada al corpus interno.")
        if self.temporal_applicability_confirmed:
            raise ValueError(
                "B.8 no puede afirmar vigencia temporal sin evidencia por unidad/caso."
            )
        if not self.requires_case_date_validation:
            raise ValueError(
                "La aplicabilidad temporal debe validarse por fecha del caso."
            )
        if self.determination_ready:
            raise ValueError(
                "B.8 no habilita por sí sola una determinación ejecutable."
            )
        if self.blocked_normative_sources:
            if (
                self.status
                is not CorpusValidationStatus.STRUCTURALLY_VALIDATED_WITH_TEMPORAL_BLOCK
            ):
                raise ValueError(
                    "Las fuentes temporalmente bloqueadas deben reflejarse en status."
                )
        elif self.status is not CorpusValidationStatus.STRUCTURALLY_VALIDATED:
            raise ValueError(
                "status temporal bloqueado requiere blocked_normative_sources."
            )
        if self.exact_normative_refs:
            if (
                self.exact_reference_status
                is not ExactReferenceValidationStatus.KNOWN_EXISTING_RULE_REFERENCE
            ):
                raise ValueError(
                    "Las referencias exactas B.6 deben estar reconocidas por B.1."
                )
        elif (
            self.exact_reference_status
            is not ExactReferenceValidationStatus.NOT_APPLICABLE
        ):
            raise ValueError(
                "Sin referencias exactas, exact_reference_status debe ser "
                "not_applicable."
            )
        return self


class ExistingRBSRuleCorpusValidation(BaseModel):
    """Validación B.8 de una regla productiva inventariada en B.1."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    rule_id: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    version: str = Field(min_length=1, max_length=50)
    normative_refs: list[str] = Field(min_length=1, max_length=50)
    corpus_reference_validated: bool = True
    temporal_validity_confirmed: bool = False
    requires_case_date_validation: bool = True
    execution_contract_unchanged: bool = True

    @model_validator(mode="after")
    def validate_existing_rule(self) -> ExistingRBSRuleCorpusValidation:
        if not self.corpus_reference_validated:
            raise ValueError(
                "La referencia de una regla B.1 debe pertenecer al corpus."
            )
        if self.temporal_validity_confirmed:
            raise ValueError("B.8 no presume vigencia temporal de reglas existentes.")
        if not self.requires_case_date_validation:
            raise ValueError(
                "La regla existente debe conservar control temporal por caso."
            )
        if not self.execution_contract_unchanged:
            raise ValueError(
                "B.8 no modifica el contrato de ejecución de reglas existentes."
            )
        return self


class PrimaryRBSCorpusValidationReport(BaseModel):
    """Reporte reproducible B.8 de validación contra el corpus interno disponible."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    validation_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    baseline_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    purpose: str = Field(min_length=20, max_length=1200)
    normative_corpus_ids: list[str] = Field(min_length=12, max_length=12)
    temporal_registry_source_sprint: str = Field(min_length=1, max_length=100)
    document_wide_temporal_blocks: list[str] = Field(
        default_factory=list, max_length=12
    )
    relation_validations: list[PrimaryRBSRelationCorpusValidation] = Field(
        min_length=1, max_length=200
    )
    existing_rule_validations: list[ExistingRBSRuleCorpusValidation] = Field(
        min_length=1, max_length=5000
    )
    temporal_policy_fail_closed: bool = True
    modifies_production_rules: bool = False

    @model_validator(mode="after")
    def validate_report(self) -> PrimaryRBSCorpusValidationReport:
        relation_ids = [item.relation_id for item in self.relation_validations]
        if len(relation_ids) != len(set(relation_ids)):
            raise ValueError("B.8 contiene relaciones duplicadas.")
        rule_keys = [
            (item.rule_id, item.version)
            for item in self.existing_rule_validations
        ]
        if len(rule_keys) != len(set(rule_keys)):
            raise ValueError("B.8 contiene reglas B.1 duplicadas.")
        if len(self.normative_corpus_ids) != len(set(self.normative_corpus_ids)):
            raise ValueError("B.8 contiene corpus normativos duplicados.")
        if not self.temporal_policy_fail_closed:
            raise ValueError("B.8 debe conservar política temporal fail-closed.")
        if self.modifies_production_rules:
            raise ValueError("B.8 valida; no modifica reglas productivas.")
        return self
