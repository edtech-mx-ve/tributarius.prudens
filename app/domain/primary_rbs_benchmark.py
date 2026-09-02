from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PrimaryRBSBenchmarkDerivationEdge(BaseModel):
    """Arista de trazabilidad que debe existir en una derivación RBS."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    producer_rule_id: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    consumer_rule_id: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    fact: str = Field(pattern=r"^[a-z][a-z0-9_]*$")


class PrimaryRBSBenchmarkCase(BaseModel):
    """Caso reproducible del benchmark RBS primario 1.0."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    case_id: str = Field(pattern=r"^B10-CASE-[0-9]{3}$")
    title: str = Field(min_length=5, max_length=200)
    facts: dict[str, Any] = Field(default_factory=dict, max_length=100)
    applicable_normative_refs: list[str] | None = Field(
        default=None,
        max_length=50,
    )
    expected_matched_rule_ids: list[str] = Field(default_factory=list, max_length=100)
    expected_absent_rule_ids: list[str] = Field(default_factory=list, max_length=100)
    required_derivation_edges: list[PrimaryRBSBenchmarkDerivationEdge] = Field(
        default_factory=list,
        max_length=100,
    )
    expected_requires_human_review: bool = False

    @field_validator(
        "applicable_normative_refs",
        "expected_matched_rule_ids",
        "expected_absent_rule_ids",
    )
    @classmethod
    def unique_optional_values(
        cls,
        values: list[str] | None,
    ) -> list[str] | None:
        if values is not None and len(values) != len(set(values)):
            raise ValueError("B.10 no admite valores duplicados.")
        return values

    @model_validator(mode="after")
    def validate_case(self) -> PrimaryRBSBenchmarkCase:
        overlap = set(self.expected_matched_rule_ids) & set(
            self.expected_absent_rule_ids
        )
        if overlap:
            raise ValueError(
                "Una regla no puede esperarse presente y ausente en el mismo caso."
            )
        edge_keys = [
            (edge.producer_rule_id, edge.consumer_rule_id, edge.fact)
            for edge in self.required_derivation_edges
        ]
        if len(edge_keys) != len(set(edge_keys)):
            raise ValueError("B.10 no admite aristas de derivación duplicadas.")
        return self


class PrimaryRBSBenchmarkSuite(BaseModel):
    """Contrato canónico del benchmark RBS B.10."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    benchmark_version: str = Field(pattern=r"^1\.\d+\.\d+$")
    baseline_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    purpose: str = Field(min_length=20, max_length=1200)
    scope_statement: str = Field(min_length=20, max_length=1200)
    cases: list[PrimaryRBSBenchmarkCase] = Field(min_length=1, max_length=200)
    required_rule_coverage: list[str] = Field(min_length=1, max_length=5000)
    expected_case_count: int = Field(ge=1)
    pass_threshold: float = Field(ge=0.0, le=1.0)
    validates_current_dataset_only: bool = True
    claims_full_mexican_tax_law_coverage: bool = False
    uses_existing_rule_engine_only: bool = True
    allows_external_legal_evidence: bool = False

    @model_validator(mode="after")
    def validate_suite(self) -> PrimaryRBSBenchmarkSuite:
        if self.expected_case_count != len(self.cases):
            raise ValueError("expected_case_count no coincide con los casos B.10.")
        case_ids = [case.case_id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("B.10 contiene case_id duplicado.")
        if len(self.required_rule_coverage) != len(set(self.required_rule_coverage)):
            raise ValueError("B.10 contiene cobertura de reglas duplicada.")
        if not self.validates_current_dataset_only:
            raise ValueError("B.10 solo valida el dataset explícito actual.")
        if self.claims_full_mexican_tax_law_coverage:
            raise ValueError("B.10 no puede afirmar cobertura total del Derecho fiscal.")
        if not self.uses_existing_rule_engine_only:
            raise ValueError("B.10 debe ejecutar exclusivamente el motor RBS existente.")
        if self.allows_external_legal_evidence:
            raise ValueError("B.10 no admite evidencia jurídica externa.")
        return self


class PrimaryRBSBenchmarkCaseResult(BaseModel):
    """Resultado observado para un caso del benchmark B.10."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    passed: bool
    matched_rule_ids: list[str]
    missing_rule_ids: list[str]
    unexpected_rule_ids: list[str]
    expected_absent_but_matched: list[str]
    missing_derivation_edges: list[str]
    unauthorized_normative_refs: list[str]
    trace_count: int = Field(ge=0)
    derivation_count: int = Field(ge=0)
    human_review_matches_expectation: bool


class PrimaryRBSBenchmarkReport(BaseModel):
    """Reporte determinista de ejecución del benchmark RBS B.10."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    benchmark_version: str
    total_cases: int = Field(ge=1)
    passed_cases: int = Field(ge=0)
    pass_rate: float = Field(ge=0.0, le=1.0)
    covered_rule_ids: list[str]
    missing_required_rule_coverage: list[str]
    rule_coverage_rate: float = Field(ge=0.0, le=1.0)
    results: list[PrimaryRBSBenchmarkCaseResult]
    threshold_met: bool
    all_passed: bool
    validates_current_dataset_only: bool = True
    claims_full_mexican_tax_law_coverage: bool = False
