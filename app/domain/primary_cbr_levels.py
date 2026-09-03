from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.cbr import CBRCase
from app.domain.primary_cbr_corpus_validation import PrimaryCBRCorpusValidationOutcome
from app.domain.primary_legal_knowledge import PrimaryManual


class PrimaryCBRKnowledgeLevel(StrEnum):
    PRIMARY = "primary"
    VALIDATED = "validated"
    OPERATIONAL = "operational"


class PrimaryCBROperationalBlocker(StrEnum):
    CORPUS_NOT_VALIDATED = "corpus_not_validated"
    REQUIRED_CASE_FIELDS_MISSING = "required_case_fields_missing"
    TEMPORAL_VALIDATION_PENDING = "temporal_validation_pending"
    RESOLUTION_OUTCOME_NOT_VERIFIED = "resolution_outcome_not_verified"
    ANONYMIZATION_REVIEW_PENDING = "anonymization_review_pending"


class PrimaryCBRLevelAssessment(BaseModel):
    """Nivel máximo alcanzado por una situación del CBR Primario 1.0."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    situation_id: str = Field(pattern=r"^(P|U)-CBR-SIT-[0-9]{3}$")
    source: PrimaryManual
    source_entry_id: str = Field(pattern=r"^(PRODECON-\d{2}|UNAM-[IVX]+)$")
    historical_regime_context: bool
    highest_level: PrimaryCBRKnowledgeLevel
    primary_level_eligible: bool = True
    validated_level_eligible: bool
    operational_level_eligible: bool
    corpus_validation_outcome: PrimaryCBRCorpusValidationOutcome
    corpus_validated: bool
    validated_normative_refs: list[str] = Field(default_factory=list, max_length=100)
    required_case_fields: list[str] = Field(min_length=5, max_length=5)
    unresolved_required_case_fields: list[str] = Field(default_factory=list, max_length=5)
    temporal_validation_pending: bool
    resolution_outcome_verified: bool = False
    anonymization_review_completed: bool = False
    legal_similarity_enabled: bool = True
    operational_blockers: list[PrimaryCBROperationalBlocker] = Field(
        default_factory=list,
        max_length=5,
    )
    operational_case_id: str | None = Field(
        default=None,
        pattern=r"^[A-Z0-9][A-Z0-9_-]{2,99}$",
    )
    operational_case_created: bool = False
    can_control_legal_decision: bool = False

    @field_validator(
        "validated_normative_refs",
        "required_case_fields",
        "unresolved_required_case_fields",
    )
    @classmethod
    def unique_strings(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("C.10 no admite valores duplicados en listas de nivel.")
        return values

    @field_validator("operational_blockers")
    @classmethod
    def unique_blockers(
        cls,
        values: list[PrimaryCBROperationalBlocker],
    ) -> list[PrimaryCBROperationalBlocker]:
        if len(values) != len(set(values)):
            raise ValueError("C.10 no admite bloqueadores operativos duplicados.")
        return values

    @model_validator(mode="after")
    def validate_level(self) -> PrimaryCBRLevelAssessment:
        expected = (
            PrimaryCBRKnowledgeLevel.OPERATIONAL
            if self.operational_level_eligible
            else PrimaryCBRKnowledgeLevel.VALIDATED
            if self.validated_level_eligible
            else PrimaryCBRKnowledgeLevel.PRIMARY
        )
        if self.highest_level is not expected:
            raise ValueError("highest_level no coincide con las compuertas C.10.")
        if not self.primary_level_eligible:
            raise ValueError("Toda situación C.2/C.3 pertenece al nivel primario.")
        if self.validated_level_eligible != self.corpus_validated:
            raise ValueError("El nivel validado C.10 debe conservar exactamente C.7.")
        if self.operational_level_eligible:
            if not self.validated_level_eligible:
                raise ValueError("Un caso operativo debe haber superado el nivel validado.")
            if self.unresolved_required_case_fields:
                raise ValueError("Un caso operativo no puede omitir campos CBR requeridos.")
            if self.temporal_validation_pending:
                raise ValueError("Un caso operativo requiere cierre temporal por caso.")
            if not self.resolution_outcome_verified:
                raise ValueError("Un caso operativo requiere resultado/resolución verificado.")
            if not self.anonymization_review_completed:
                raise ValueError("Un caso operativo requiere revisión de anonimización.")
            if self.operational_blockers:
                raise ValueError("Un caso operativo no puede conservar bloqueadores.")
            if not self.operational_case_created or self.operational_case_id is None:
                raise ValueError("El nivel operativo debe materializar un CBRCase existente.")
        else:
            if self.operational_case_created or self.operational_case_id is not None:
                raise ValueError("C.10 no puede materializar un caso que no sea operativo.")
            if not self.operational_blockers:
                raise ValueError("Toda situación no operativa debe explicar su bloqueo.")
        if self.can_control_legal_decision:
            raise ValueError("Ningún nivel CBR puede controlar Legal Decision.")
        return self


class PrimaryCBRLevelRegistry(BaseModel):
    """Registro C.10 de promoción primary -> validated -> operational."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    baseline_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    purpose: str = Field(min_length=20, max_length=1200)
    existing_cbr_case_model: str = "app.domain.cbr.CBRCase"
    existing_cbr_loader: str = "app.services.cbr_loader.load_cbr_cases_jsonl"
    existing_cbr_anonymizer: str = "app.services.cbr_anonymizer.anonymize_text"
    source_situation_count: int = Field(ge=1)
    primary_membership_count: int = Field(ge=1)
    validated_membership_count: int = Field(ge=0)
    operational_membership_count: int = Field(ge=0)
    highest_level_counts: dict[str, int] = Field(min_length=3, max_length=3)
    operational_shape_complete_count: int = Field(ge=0)
    validated_shape_complete_count: int = Field(ge=0)
    operational_blocker_counts: dict[str, int] = Field(min_length=1, max_length=10)
    assessments: list[PrimaryCBRLevelAssessment] = Field(min_length=1)
    operational_cases: list[CBRCase] = Field(default_factory=list)
    preserves_c7_blocks: bool = True
    reuses_existing_cbr_case_contract: bool = True
    requires_temporal_validation_for_operational: bool = True
    requires_verified_resolution_for_operational: bool = True
    requires_human_anonymization_review_for_operational: bool = True
    persists_operational_cases: bool = False
    modifies_existing_cbr_engine: bool = False
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def validate_registry(self) -> PrimaryCBRLevelRegistry:
        if self.source_situation_count != len(self.assessments):
            raise ValueError("source_situation_count no coincide con C.10.")
        ids = [item.situation_id for item in self.assessments]
        if len(ids) != len(set(ids)):
            raise ValueError("C.10 contiene situaciones duplicadas.")
        if self.primary_membership_count != self.source_situation_count:
            raise ValueError("El nivel primario debe contener las 37 situaciones fuente.")
        validated = sum(item.validated_level_eligible for item in self.assessments)
        operational = sum(item.operational_level_eligible for item in self.assessments)
        if self.validated_membership_count != validated:
            raise ValueError("validated_membership_count no coincide con C.10.")
        if self.operational_membership_count != operational:
            raise ValueError("operational_membership_count no coincide con C.10.")
        expected_highest = {level.value: 0 for level in PrimaryCBRKnowledgeLevel}
        for item in self.assessments:
            expected_highest[item.highest_level.value] += 1
        if self.highest_level_counts != expected_highest:
            raise ValueError("highest_level_counts no coincide con C.10.")
        expected_blockers = {blocker.value: 0 for blocker in PrimaryCBROperationalBlocker}
        for item in self.assessments:
            for blocker in item.operational_blockers:
                expected_blockers[blocker.value] += 1
        if self.operational_blocker_counts != expected_blockers:
            raise ValueError("operational_blocker_counts no coincide con C.10.")
        if self.operational_membership_count != len(self.operational_cases):
            raise ValueError("Los CBRCase operativos no coinciden con el nivel operativo.")
        operational_ids = {case.case_id for case in self.operational_cases}
        expected_ids = {
            item.operational_case_id
            for item in self.assessments
            if item.operational_level_eligible
        }
        if operational_ids != expected_ids:
            raise ValueError("Los CBRCase materializados no coinciden con las evaluaciones C.10.")
        if not all(
            (
                self.preserves_c7_blocks,
                self.reuses_existing_cbr_case_contract,
                self.requires_temporal_validation_for_operational,
                self.requires_verified_resolution_for_operational,
                self.requires_human_anonymization_review_for_operational,
            )
        ):
            raise ValueError("C.10 debe mantener todas las compuertas de seguridad declaradas.")
        if any(
            (
                self.persists_operational_cases,
                self.modifies_existing_cbr_engine,
                self.can_control_legal_decision,
            )
        ):
            raise ValueError("C.10 clasifica niveles sin persistir ni reemplazar el CBR existente.")
        return self
