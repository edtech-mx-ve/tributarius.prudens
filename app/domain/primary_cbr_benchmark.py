from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.cbr import CaseField
from app.domain.primary_cbr_corpus_validation import PrimaryCBRCorpusValidationOutcome
from app.domain.primary_cbr_legal_similarity import PrimaryCBRLegalSimilarityDecision
from app.domain.primary_cbr_levels import PrimaryCBRKnowledgeLevel


class PrimaryCBRBenchmarkCaseKind(StrEnum):
    SITUATION = "situation"
    SIMILARITY_PAIR = "similarity_pair"


class PrimaryCBRBenchmarkDimension(StrEnum):
    PROBLEM_INSTITUTION = "problem_institution"
    CORPUS_VALIDATION = "corpus_validation"
    FAMILY_ASSIGNMENT = "family_assignment"
    LEGAL_SIMILARITY = "legal_similarity"
    HISTORICAL_SAFETY = "historical_safety"
    LEVEL_PROMOTION = "level_promotion"


class PrimaryCBRBenchmarkCase(BaseModel):
    """Caso reproducible del benchmark CBR Primario C.11."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    case_id: str = Field(pattern=r"^C11-CASE-[0-9]{3}$")
    title: str = Field(min_length=5, max_length=220)
    kind: PrimaryCBRBenchmarkCaseKind
    dimensions: list[PrimaryCBRBenchmarkDimension] = Field(min_length=1, max_length=6)

    situation_id: str | None = Field(default=None, pattern=r"^(P|U)-CBR-SIT-[0-9]{3}$")
    expected_problem_id: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]*$")
    expected_institution_id: str | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9_]*$",
    )
    expect_institution_absent: bool = False
    expected_primary_family_id: str | None = Field(default=None, pattern=r"^CBR-[A-Z]+$")
    required_family_ids: list[str] = Field(default_factory=list, max_length=12)
    expected_corpus_outcome: PrimaryCBRCorpusValidationOutcome | None = None
    expected_corpus_validated: bool | None = None
    expected_highest_level: PrimaryCBRKnowledgeLevel | None = None
    expected_validated_level_eligible: bool | None = None
    expected_operational_level_eligible: bool | None = None
    expected_historical_regime_context: bool | None = None

    left_situation_id: str | None = Field(
        default=None,
        pattern=r"^(P|U)-CBR-SIT-[0-9]{3}$",
    )
    right_situation_id: str | None = Field(
        default=None,
        pattern=r"^(P|U)-CBR-SIT-[0-9]{3}$",
    )
    expected_similarity_decision: PrimaryCBRLegalSimilarityDecision | None = None
    expected_similarity: float | None = Field(default=None, ge=0, le=1)
    expected_conflict_fields: list[CaseField] = Field(default_factory=list, max_length=3)
    expected_left_neighbor_rank: int | None = Field(default=None, ge=1, le=20)

    @field_validator("dimensions")
    @classmethod
    def unique_dimensions(
        cls,
        values: list[PrimaryCBRBenchmarkDimension],
    ) -> list[PrimaryCBRBenchmarkDimension]:
        if len(values) != len(set(values)):
            raise ValueError("C.11 no admite dimensiones duplicadas por caso.")
        return values

    @field_validator("required_family_ids")
    @classmethod
    def unique_family_ids(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("C.11 no admite familias duplicadas por caso.")
        return values

    @field_validator("expected_conflict_fields")
    @classmethod
    def unique_conflict_fields(cls, values: list[CaseField]) -> list[CaseField]:
        if len(values) != len(set(values)):
            raise ValueError("C.11 no admite campos críticos duplicados por caso.")
        return values

    @model_validator(mode="after")
    def validate_case_shape(self) -> PrimaryCBRBenchmarkCase:
        if self.kind is PrimaryCBRBenchmarkCaseKind.SITUATION:
            if self.situation_id is None:
                raise ValueError("Un caso situation C.11 requiere situation_id.")
            if self.left_situation_id is not None or self.right_situation_id is not None:
                raise ValueError("Un caso situation C.11 no puede declarar un par de similitud.")
            if self.expected_similarity_decision is not None:
                raise ValueError("Un caso situation C.11 no puede fijar decisión de similitud.")
            situation_expectations = (
                self.expected_problem_id,
                self.expected_institution_id,
                self.expected_primary_family_id,
                self.expected_corpus_outcome,
                self.expected_corpus_validated,
                self.expected_highest_level,
                self.expected_validated_level_eligible,
                self.expected_operational_level_eligible,
                self.expected_historical_regime_context,
            )
            if (
                not self.required_family_ids
                and not self.expect_institution_absent
                and all(value is None for value in situation_expectations)
            ):
                raise ValueError("Un caso situation C.11 debe contener expectativas observables.")
        else:
            if self.situation_id is not None:
                raise ValueError("Un caso similarity_pair C.11 no usa situation_id único.")
            if self.left_situation_id is None or self.right_situation_id is None:
                raise ValueError("Un caso similarity_pair C.11 requiere ambos IDs.")
            if self.left_situation_id == self.right_situation_id:
                raise ValueError("C.11 no compara una situación consigo misma.")
            if self.expected_similarity_decision is None:
                raise ValueError("Un par C.11 requiere expected_similarity_decision.")
            if self.expected_left_neighbor_rank is not None and (
                self.expected_similarity_decision is not PrimaryCBRLegalSimilarityDecision.ELIGIBLE
            ):
                raise ValueError("Sólo un par elegible C.11 puede exigir rango de vecino.")
            if PrimaryCBRBenchmarkDimension.LEGAL_SIMILARITY not in self.dimensions:
                raise ValueError("Los pares C.11 deben cubrir legal_similarity.")
        return self


class PrimaryCBRBenchmarkSuite(BaseModel):
    """Contrato canónico del benchmark CBR Primario 1.0."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    benchmark_version: str = Field(pattern=r"^1\.\d+\.\d+$")
    baseline_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    purpose: str = Field(min_length=20, max_length=1400)
    scope_statement: str = Field(min_length=20, max_length=1400)
    cases: list[PrimaryCBRBenchmarkCase] = Field(min_length=1, max_length=100)
    required_dimensions: list[PrimaryCBRBenchmarkDimension] = Field(min_length=6, max_length=6)
    expected_case_count: int = Field(ge=1)
    pass_threshold: float = Field(ge=0, le=1)
    expected_source_situation_count: int = Field(ge=1)
    expected_validated_membership_count: int = Field(ge=0)
    expected_operational_membership_count: int = Field(ge=0)
    expected_similarity_profile_count: int = Field(ge=1)
    expected_total_pair_count: int = Field(ge=0)
    expected_eligible_pair_count: int = Field(ge=0)
    validates_current_dataset_only: bool = True
    claims_full_mexican_tax_law_coverage: bool = False
    uses_existing_cbr_similarity: bool = True
    allows_external_legal_evidence: bool = False
    creates_operational_cases: bool = False

    @field_validator("required_dimensions")
    @classmethod
    def unique_dimensions(
        cls,
        values: list[PrimaryCBRBenchmarkDimension],
    ) -> list[PrimaryCBRBenchmarkDimension]:
        if len(values) != len(set(values)):
            raise ValueError("C.11 no admite dimensiones duplicadas.")
        return values

    @model_validator(mode="after")
    def validate_suite(self) -> PrimaryCBRBenchmarkSuite:
        if self.expected_case_count != len(self.cases):
            raise ValueError("expected_case_count no coincide con los casos C.11.")
        case_ids = [case.case_id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("C.11 contiene case_id duplicado.")
        if set(self.required_dimensions) != set(PrimaryCBRBenchmarkDimension):
            raise ValueError("C.11 debe cubrir exactamente las seis dimensiones declaradas.")
        if self.pass_threshold != 1.0:
            raise ValueError("C.11 exige aprobación perfecta del dataset benchmark actual.")
        if not self.validates_current_dataset_only:
            raise ValueError("C.11 sólo valida el dataset explícito actual.")
        if self.claims_full_mexican_tax_law_coverage:
            raise ValueError("C.11 no puede afirmar cobertura total del Derecho fiscal mexicano.")
        if not self.uses_existing_cbr_similarity:
            raise ValueError("C.11 debe reutilizar la similitud CBR existente extendida en C.9.")
        if self.allows_external_legal_evidence or self.creates_operational_cases:
            raise ValueError("C.11 no admite evidencia externa ni crea casos operativos.")
        return self


class PrimaryCBRBenchmarkCaseResult(BaseModel):
    """Resultado observado de un caso C.11."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    passed: bool
    dimensions: list[PrimaryCBRBenchmarkDimension]
    diagnostics: list[str]
    observed_similarity_decision: PrimaryCBRLegalSimilarityDecision | None = None
    observed_similarity: float | None = Field(default=None, ge=0, le=1)
    observed_conflict_fields: list[CaseField] = Field(default_factory=list, max_length=3)


class PrimaryCBRBenchmarkReport(BaseModel):
    """Reporte determinista del benchmark CBR C.11."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    benchmark_version: str
    total_cases: int = Field(ge=1)
    passed_cases: int = Field(ge=0)
    pass_rate: float = Field(ge=0, le=1)
    covered_dimensions: list[PrimaryCBRBenchmarkDimension]
    missing_required_dimensions: list[PrimaryCBRBenchmarkDimension]
    global_contract_passed: bool
    results: list[PrimaryCBRBenchmarkCaseResult]
    threshold_met: bool
    all_passed: bool
    validates_current_dataset_only: bool = True
    claims_full_mexican_tax_law_coverage: bool = False
    uses_existing_cbr_similarity: bool = True
    allows_external_legal_evidence: bool = False
    creates_operational_cases: bool = False
