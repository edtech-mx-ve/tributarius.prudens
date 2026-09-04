from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.jurisprudence_decision_application import (
    JurisprudenceCaseApplicationStatus,
    JurisprudenceDecisionEffect,
)
from app.domain.jurisprudence_evidence import JurisprudenceEvidenceDecision


class JurisprudenceBenchmarkScenario(StrEnum):
    WITHOUT_JURISPRUDENCE = "without_jurisprudence"
    UNRELATED_NORM = "unrelated_norm"
    CITATION_ONLY = "citation_only"
    NOT_YET_MANDATORY = "not_yet_mandatory"
    MISSING_JUSTIFICATION = "missing_justification"
    HARD_MATERIAL_CONFLICT = "hard_material_conflict"
    MANDATORY_APPLICABLE = "mandatory_applicable"
    REFERENCE_2032043 = "reference_2032043"


class JurisprudenceBenchmarkCase(BaseModel):
    """Caso reproducible E.7 sobre las fronteras E.1-E.6."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    case_id: str = Field(pattern=r"^E7-CASE-[0-9]{3}$")
    title: str = Field(min_length=5, max_length=220)
    scenario: JurisprudenceBenchmarkScenario
    query: str = Field(min_length=10, max_length=1800)
    query_date: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    applicable_normative_refs: list[str] = Field(min_length=1, max_length=20)
    expected_retrieved_count: int = Field(ge=0, le=20)
    expected_authorized_evidence_count: int = Field(ge=0, le=20)
    expected_evidence_decisions: list[JurisprudenceEvidenceDecision] = Field(
        default_factory=list,
        max_length=20,
    )
    expected_application_statuses: list[JurisprudenceCaseApplicationStatus] = Field(
        default_factory=list,
        max_length=20,
    )
    expected_decision_effects: list[JurisprudenceDecisionEffect] = Field(
        default_factory=list,
        max_length=20,
    )
    expected_binding_jurisprudence_applies: bool
    expected_requires_human_review: bool
    reference_thesis_2032043: bool = False

    @field_validator(
        "applicable_normative_refs",
        "expected_evidence_decisions",
        "expected_application_statuses",
        "expected_decision_effects",
    )
    @classmethod
    def unique_values(cls, values: list[object]) -> list[object]:
        if len(values) != len(set(values)):
            raise ValueError("E.7 no admite expectativas duplicadas por caso.")
        return values

    @model_validator(mode="after")
    def validate_case(self) -> JurisprudenceBenchmarkCase:
        without = self.scenario is JurisprudenceBenchmarkScenario.WITHOUT_JURISPRUDENCE
        if without:
            if self.expected_retrieved_count != 0:
                raise ValueError("El control E.7 sin jurisprudencia no puede recuperar páginas.")
            if self.expected_authorized_evidence_count != 0:
                raise ValueError("El control E.7 sin jurisprudencia no admite evidencia.")
            if self.expected_evidence_decisions or self.expected_application_statuses:
                raise ValueError("El control E.7 sin jurisprudencia no produce evaluaciones.")
            if self.expected_binding_jurisprudence_applies:
                raise ValueError("Sin jurisprudencia no puede existir interpretación vinculante.")
        if self.reference_thesis_2032043 != (
            self.scenario is JurisprudenceBenchmarkScenario.REFERENCE_2032043
        ):
            raise ValueError("La marca de referencia 2032043 debe coincidir con su escenario.")
        return self


class JurisprudenceBenchmarkSuite(BaseModel):
    """Contrato E.7 del benchmark de jurisprudencia opcional."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    benchmark_version: str = Field(pattern=r"^1\.\d+\.\d+$")
    baseline_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    purpose: str = Field(min_length=20, max_length=1600)
    scope_statement: str = Field(min_length=20, max_length=1600)
    cases: list[JurisprudenceBenchmarkCase] = Field(min_length=8, max_length=40)
    expected_case_count: int = Field(ge=8, le=40)
    pass_threshold: float = Field(ge=0.0, le=1.0)
    validates_current_dataset_only: bool = True
    claims_full_mexican_jurisprudence_coverage: bool = False
    jurisprudence_is_optional: bool = True
    session_scope_required: bool = True
    justification_is_ratio_source: bool = True
    thematic_similarity_can_establish_applicability: bool = False
    jurisprudence_can_replace_normative_basis: bool = False
    jurisprudence_can_create_second_conclusion: bool = False
    allows_web_jurisprudence: bool = False

    @model_validator(mode="after")
    def validate_suite(self) -> JurisprudenceBenchmarkSuite:
        if self.expected_case_count != len(self.cases):
            raise ValueError("expected_case_count no coincide con los casos E.7.")
        case_ids = [case.case_id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("E.7 contiene case_id duplicado.")
        scenarios = {case.scenario for case in self.cases}
        if scenarios != set(JurisprudenceBenchmarkScenario):
            raise ValueError("E.7 debe cubrir exactamente los ocho escenarios definidos.")
        if self.pass_threshold != 1.0:
            raise ValueError("E.7 exige aprobación perfecta del benchmark actual.")
        if not self.jurisprudence_is_optional or not self.session_scope_required:
            raise ValueError("E.7 debe preservar jurisprudencia opcional y de sesión.")
        if not self.justification_is_ratio_source:
            raise ValueError("E.7 exige Justificación como fuente de ratio decidendi.")
        if self.thematic_similarity_can_establish_applicability:
            raise ValueError("E.7 prohíbe aplicabilidad por mera similitud temática.")
        if self.jurisprudence_can_replace_normative_basis:
            raise ValueError("E.7 no permite sustituir la base normativa.")
        if self.jurisprudence_can_create_second_conclusion:
            raise ValueError("E.7 debe preservar una única conclusión jurídica.")
        if self.allows_web_jurisprudence:
            raise ValueError("E.7 sólo admite jurisprudencia expresamente anexada.")
        return self


class JurisprudenceBenchmarkCaseResult(BaseModel):
    """Resultado observado de un caso E.7."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    scenario: JurisprudenceBenchmarkScenario
    passed: bool
    diagnostics: list[str]
    retrieved_count: int
    authorized_evidence_count: int
    evidence_decisions: list[JurisprudenceEvidenceDecision]
    application_statuses: list[JurisprudenceCaseApplicationStatus]
    decision_effects: list[JurisprudenceDecisionEffect]
    binding_jurisprudence_applies: bool
    requires_human_review: bool
    session_scope_preserved: bool
    justification_ratio_boundary_preserved: bool
    normative_basis_preserved: bool
    single_conclusion_preserved: bool
    reference_thesis_2032043: bool


class JurisprudenceBenchmarkReport(BaseModel):
    """Reporte reproducible E.7 de cierre del Bloque E."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str
    benchmark_version: str
    total_cases: int
    passed_cases: int
    pass_rate: float
    pass_threshold: float
    threshold_met: bool
    all_passed: bool
    results: list[JurisprudenceBenchmarkCaseResult]
    without_jurisprudence_case_passed: bool
    reference_thesis_2032043_passed: bool
    optionality_contract_passed: bool
    session_scope_contract_passed: bool
    ratio_justification_contract_passed: bool
    normative_basis_contract_passed: bool
    single_conclusion_contract_passed: bool
    validates_current_dataset_only: bool
    claims_full_mexican_jurisprudence_coverage: bool
