from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.query import QueryDimensionName, QueryIntent, TemporalYearResolution


class HeuristicNavigationBenchmarkDimension(StrEnum):
    QUERY_ANALYSIS = "query_analysis"
    PRIMARY_ACTIVATION = "primary_activation"
    RBS_ORIENTATION = "rbs_orientation"
    CBR_ORIENTATION = "cbr_orientation"
    NORMATIVE_RANKING = "normative_ranking"
    STRUCTURAL_NAVIGATION = "structural_navigation"
    FOCUSED_RAG = "focused_rag"
    FULL_CORPUS_EXPANSION = "full_corpus_expansion"
    TEMPORAL_CONTROL = "temporal_control"


class HeuristicNavigationBenchmarkCase(BaseModel):
    """Caso reproducible D.10 sobre la cadena heurística D.1-D.9."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    case_id: str = Field(pattern=r"^D10-CASE-[0-9]{3}$")
    title: str = Field(min_length=5, max_length=220)
    query: str = Field(min_length=10, max_length=1600)
    dimensions: list[HeuristicNavigationBenchmarkDimension] = Field(
        min_length=1,
        max_length=9,
    )
    resico_case: bool = False
    expected_primary_intent: QueryIntent
    expected_dimension_values: dict[QueryDimensionName, list[str]] = Field(
        default_factory=dict,
        max_length=7,
    )
    expected_problem_id: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]*$")
    expect_problem_absent: bool = False
    expected_institution_id: str | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9_]*$",
    )
    expect_institution_absent: bool = False
    required_primary_entry_ids: list[str] = Field(default_factory=list, max_length=19)
    forbidden_primary_entry_ids: list[str] = Field(default_factory=list, max_length=19)
    required_rbs_relation_ids: list[str] = Field(default_factory=list, max_length=18)
    expected_cbr_primary_family_id: str | None = Field(
        default=None,
        pattern=r"^CBR-[A-Z]+$",
    )
    expect_cbr_family_absent: bool = False
    minimum_cbr_match_count: int = Field(default=0, ge=0, le=20)
    required_cbr_situation_ids: list[str] = Field(default_factory=list, max_length=20)
    forbidden_cbr_situation_ids: list[str] = Field(default_factory=list, max_length=20)
    expected_focus_source_ids: list[str] = Field(default_factory=list, max_length=5)
    required_exact_normative_refs: list[str] = Field(default_factory=list, max_length=40)
    expected_rag_plan_applied: bool
    expected_expansion_source_count: int = Field(ge=7, le=12)
    expected_explicit_query_years: list[int] = Field(default_factory=list, max_length=20)
    expected_historical_context: bool = False
    required_temporal_blocked_source_ids: list[str] = Field(default_factory=list, max_length=12)
    expected_year_resolution: TemporalYearResolution
    expected_resolved_fiscal_year: int | None = Field(default=None, ge=1900, le=2200)

    @field_validator("dimensions")
    @classmethod
    def unique_case_dimensions(
        cls,
        values: list[HeuristicNavigationBenchmarkDimension],
    ) -> list[HeuristicNavigationBenchmarkDimension]:
        if len(values) != len(set(values)):
            raise ValueError("D.10 no admite dimensiones duplicadas por caso.")
        return values

    @field_validator(
        "required_primary_entry_ids",
        "forbidden_primary_entry_ids",
        "required_rbs_relation_ids",
        "required_cbr_situation_ids",
        "forbidden_cbr_situation_ids",
        "expected_focus_source_ids",
        "required_exact_normative_refs",
        "required_temporal_blocked_source_ids",
    )
    @classmethod
    def unique_string_values(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("D.10 no admite expectativas de texto duplicadas.")
        return values

    @field_validator("expected_explicit_query_years")
    @classmethod
    def unique_query_years(cls, values: list[int]) -> list[int]:
        if len(values) != len(set(values)):
            raise ValueError("D.10 no admite años explícitos duplicados.")
        return values

    @field_validator("expected_dimension_values")
    @classmethod
    def unique_dimension_values(
        cls,
        values: dict[QueryDimensionName, list[str]],
    ) -> dict[QueryDimensionName, list[str]]:
        for dimension_values in values.values():
            if len(dimension_values) != len(set(dimension_values)):
                raise ValueError("D.10 no admite valores dimensionales duplicados.")
        return values

    @model_validator(mode="after")
    def validate_case(self) -> HeuristicNavigationBenchmarkCase:
        overlap = set(self.required_primary_entry_ids) & set(
            self.forbidden_primary_entry_ids
        )
        if overlap:
            raise ValueError("D.10 no puede exigir y prohibir la misma entrada primaria.")
        cbr_overlap = set(self.required_cbr_situation_ids) & set(
            self.forbidden_cbr_situation_ids
        )
        if cbr_overlap:
            raise ValueError("D.10 no puede exigir y prohibir el mismo caso CBR.")
        if self.expected_problem_id is not None and self.expect_problem_absent:
            raise ValueError("D.10 no puede esperar problema presente y ausente.")
        if self.expected_institution_id is not None and self.expect_institution_absent:
            raise ValueError("D.10 no puede esperar institución presente y ausente.")
        if self.expected_cbr_primary_family_id is not None and self.expect_cbr_family_absent:
            raise ValueError("D.10 no puede esperar familia CBR presente y ausente.")
        if self.expected_rag_plan_applied != bool(self.expected_focus_source_ids):
            raise ValueError("D.10 debe alinear plan RAG esperado y foco esperado.")
        if self.expected_expansion_source_count != 12 - len(self.expected_focus_source_ids):
            raise ValueError("D.10 debe expandir exactamente los corpus fuera del foco.")
        return self


class HeuristicNavigationBenchmarkSuite(BaseModel):
    """Contrato canónico D.10 del benchmark del motor heurístico D.1-D.9."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    benchmark_version: str = Field(pattern=r"^1\.\d+\.\d+$")
    baseline_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    purpose: str = Field(min_length=20, max_length=1600)
    scope_statement: str = Field(min_length=20, max_length=1600)
    cases: list[HeuristicNavigationBenchmarkCase] = Field(min_length=1, max_length=100)
    required_dimensions: list[HeuristicNavigationBenchmarkDimension] = Field(
        min_length=9,
        max_length=9,
    )
    expected_case_count: int = Field(ge=1)
    expected_resico_case_count: int = Field(ge=1)
    expected_normative_corpus_count: int = Field(ge=12, le=12)
    pass_threshold: float = Field(ge=0, le=1)
    validates_current_dataset_only: bool = True
    claims_full_mexican_tax_law_coverage: bool = False
    uses_runtime_query_analyzer: bool = True
    preserves_full_normative_corpus: bool = True
    allows_external_legal_evidence: bool = False
    can_control_legal_decision: bool = False

    @field_validator("required_dimensions")
    @classmethod
    def unique_dimensions(
        cls,
        values: list[HeuristicNavigationBenchmarkDimension],
    ) -> list[HeuristicNavigationBenchmarkDimension]:
        if len(values) != len(set(values)):
            raise ValueError("D.10 no admite dimensiones benchmark duplicadas.")
        return values

    @model_validator(mode="after")
    def validate_suite(self) -> HeuristicNavigationBenchmarkSuite:
        if self.expected_case_count != len(self.cases):
            raise ValueError("expected_case_count no coincide con los casos D.10.")
        if self.expected_resico_case_count != sum(case.resico_case for case in self.cases):
            raise ValueError("expected_resico_case_count no coincide con los casos RESICO.")
        case_ids = [case.case_id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("D.10 contiene case_id duplicado.")
        if set(self.required_dimensions) != set(HeuristicNavigationBenchmarkDimension):
            raise ValueError("D.10 debe cubrir exactamente las nueve capas D.1-D.9.")
        if self.pass_threshold != 1.0:
            raise ValueError("D.10 exige aprobación perfecta del dataset benchmark actual.")
        if self.expected_normative_corpus_count != 12:
            raise ValueError("D.10 debe preservar exactamente los 12 corpus A.8.")
        if not self.validates_current_dataset_only:
            raise ValueError("D.10 sólo valida el dataset explícito actual.")
        if self.claims_full_mexican_tax_law_coverage:
            raise ValueError("D.10 no puede afirmar cobertura total del Derecho fiscal mexicano.")
        if not self.uses_runtime_query_analyzer or not self.preserves_full_normative_corpus:
            raise ValueError("D.10 debe ejecutar la cadena real D.1-D.9 y preservar A.8.")
        if self.allows_external_legal_evidence or self.can_control_legal_decision:
            raise ValueError("D.10 no admite evidencia externa ni controla Legal Decision.")
        return self


class HeuristicNavigationBenchmarkCaseResult(BaseModel):
    """Resultado observado de un caso D.10."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    passed: bool
    resico_case: bool
    diagnostics: list[str]
    observed_focus_source_ids: list[str]
    observed_primary_entry_ids: list[str]
    observed_rbs_relation_ids: list[str]
    observed_cbr_situation_ids: list[str]
    observed_explicit_query_years: list[int]
    observed_year_resolution: TemporalYearResolution
    observed_resolved_fiscal_year: int | None = None
    full_corpus_preserved: bool
    legal_decision_boundary_preserved: bool


class HeuristicNavigationBenchmarkReport(BaseModel):
    """Reporte determinista D.10 del motor heurístico y de navegación."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    benchmark_version: str
    total_cases: int = Field(ge=1)
    passed_cases: int = Field(ge=0)
    pass_rate: float = Field(ge=0, le=1)
    resico_cases: int = Field(ge=1)
    passed_resico_cases: int = Field(ge=0)
    covered_dimensions: list[HeuristicNavigationBenchmarkDimension]
    missing_required_dimensions: list[HeuristicNavigationBenchmarkDimension]
    full_corpus_contract_passed: bool
    legal_decision_boundary_passed: bool
    results: list[HeuristicNavigationBenchmarkCaseResult]
    threshold_met: bool
    all_passed: bool
    validates_current_dataset_only: bool = True
    claims_full_mexican_tax_law_coverage: bool = False
