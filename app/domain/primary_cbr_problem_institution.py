from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.primary_legal_knowledge import FiscalProblemInstitutionKind, PrimaryManual


class PrimaryCBRClassificationBasis(StrEnum):
    """Base permitida para clasificar problema/institución en C.5."""

    A6_PRIMARY_ENTRY_AND_C4_FACTS = "a6_primary_entry_and_c4_facts"


class PrimaryCBRConceptClassification(BaseModel):
    """Correspondencia taxonómica A.6 respaldada por hechos C.4."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    concept_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=3, max_length=160)
    kind: FiscalProblemInstitutionKind
    primary: bool
    evidence_fact_ids: list[str] = Field(min_length=1, max_length=20)
    basis: PrimaryCBRClassificationBasis = (
        PrimaryCBRClassificationBasis.A6_PRIMARY_ENTRY_AND_C4_FACTS
    )
    taxonomic_only: bool = True
    requires_normative_validation: bool = True
    can_control_legal_decision: bool = False

    @field_validator("evidence_fact_ids")
    @classmethod
    def unique_evidence(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("C.5 no admite evidencia de hechos duplicada.")
        return values

    @model_validator(mode="after")
    def validate_boundary(self) -> PrimaryCBRConceptClassification:
        if not self.taxonomic_only or not self.requires_normative_validation:
            raise ValueError("C.5 sólo clasifica taxonómicamente y exige validación normativa.")
        if self.can_control_legal_decision:
            raise ValueError("Una clasificación C.5 no puede controlar Legal Decision.")
        return self


class PrimaryCBRClassifiedSimilaritySeed(BaseModel):
    """Semilla CBR C.4 con problem_type taxonómico cuando existe match exacto A.6."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    taxpayer_type: str | None = Field(default=None, max_length=100)
    activity: str | None = Field(default=None, max_length=200)
    tax: str | None = Field(default=None, max_length=100)
    problem_type: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]*$")
    authority_act: str | None = Field(default=None, max_length=200)
    procedural_stage: str | None = Field(default=None, max_length=200)
    fiscal_year: int | None = Field(default=None, ge=1900, le=2200)
    evidence_fact_ids: dict[str, list[str]] = Field(default_factory=dict, max_length=7)

    @field_validator("taxpayer_type")
    @classmethod
    def canonical_taxpayer_type(cls, value: str | None) -> str | None:
        if value is not None and value not in {"individual", "legal_entity"}:
            raise ValueError("C.5 preserva los tipos de contribuyente canónicos del CBR.")
        return value

    @field_validator("tax")
    @classmethod
    def canonical_tax(cls, value: str | None) -> str | None:
        if value is not None and value not in {"ISR", "IVA"}:
            raise ValueError("C.5 preserva únicamente ISR/IVA ya fijados por C.4.")
        return value

    @model_validator(mode="after")
    def validate_evidence(self) -> PrimaryCBRClassifiedSimilaritySeed:
        populated = {
            "taxpayer_type": self.taxpayer_type,
            "activity": self.activity,
            "tax": self.tax,
            "problem_type": self.problem_type,
            "authority_act": self.authority_act,
            "procedural_stage": self.procedural_stage,
            "fiscal_year": self.fiscal_year,
        }
        if set(self.evidence_fact_ids) - set(populated):
            raise ValueError("La evidencia C.5 sólo puede apuntar a campos CBR existentes.")
        for field_name, value in populated.items():
            evidence = self.evidence_fact_ids.get(field_name, [])
            if value is not None and not evidence:
                raise ValueError(f"Falta evidencia para el campo CBR {field_name}.")
            if value is None and evidence:
                raise ValueError(f"Hay evidencia para un campo CBR vacío: {field_name}.")
        return self


class PrimaryCBRProblemInstitutionSituation(BaseModel):
    """Resultado C.5 por situación fuente, todavía no caso CBR operativo."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    situation_id: str = Field(pattern=r"^(P|U)-CBR-SIT-[0-9]{3}$")
    source: PrimaryManual
    source_entry_id: str = Field(pattern=r"^(PRODECON-\d{2}|UNAM-[IVX]+)$")
    historical_regime_context: bool
    primary_problem_id: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]*$")
    problem_matches: list[PrimaryCBRConceptClassification] = Field(
        default_factory=list, max_length=6
    )
    problem_no_exact_match_reason: str | None = Field(default=None, max_length=500)
    primary_institution_id: str | None = Field(
        default=None, pattern=r"^[a-z][a-z0-9_]*$"
    )
    institution_matches: list[PrimaryCBRConceptClassification] = Field(
        default_factory=list, max_length=6
    )
    institution_no_exact_match_reason: str | None = Field(default=None, max_length=500)
    similarity_seed: PrimaryCBRClassifiedSimilaritySeed
    unresolved_required_case_fields: list[str] = Field(default_factory=list, max_length=5)
    facts_normalized: bool = True
    problem_institution_classified: bool = True
    normative_articles_linked: bool = False
    corpus_validated: bool = False
    cbr_family_assigned: bool = False
    operational_case_created: bool = False
    can_control_legal_decision: bool = False

    @field_validator("unresolved_required_case_fields")
    @classmethod
    def unique_unresolved(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("C.5 no admite campos requeridos duplicados.")
        return values

    @model_validator(mode="after")
    def validate_classification(self) -> PrimaryCBRProblemInstitutionSituation:
        problem_ids = [match.concept_id for match in self.problem_matches]
        institution_ids = [match.concept_id for match in self.institution_matches]
        if len(problem_ids) != len(set(problem_ids)) or len(institution_ids) != len(
            set(institution_ids)
        ):
            raise ValueError("C.5 no admite conceptos clasificados duplicados.")
        if any(
            match.kind is not FiscalProblemInstitutionKind.PROBLEM
            for match in self.problem_matches
        ):
            raise ValueError("problem_matches sólo puede contener problemas A.6.")
        if any(
            match.kind is not FiscalProblemInstitutionKind.INSTITUTION
            for match in self.institution_matches
        ):
            raise ValueError("institution_matches sólo puede contener instituciones A.6.")

        primary_problems = [match.concept_id for match in self.problem_matches if match.primary]
        primary_institutions = [
            match.concept_id for match in self.institution_matches if match.primary
        ]
        if self.primary_problem_id is None:
            if self.problem_matches or not self.problem_no_exact_match_reason:
                raise ValueError("Sin problema exacto C.5 debe explicarse el no-match A.6.")
            if self.similarity_seed.problem_type is not None:
                raise ValueError("Sin problema A.6 no puede fijarse problem_type.")
            if "problem_type" not in self.unresolved_required_case_fields:
                raise ValueError("problem_type debe seguir pendiente cuando no hay match A.6.")
        else:
            if primary_problems != [self.primary_problem_id]:
                raise ValueError("C.5 exige exactamente un problema primario coherente.")
            if self.problem_no_exact_match_reason is not None:
                raise ValueError("No corresponde razón de no-match cuando existe problema C.5.")
            if self.similarity_seed.problem_type != self.primary_problem_id:
                raise ValueError("problem_type debe ser el concept_id del problema primario A.6.")
            if "problem_type" in self.unresolved_required_case_fields:
                raise ValueError("problem_type no puede seguir pendiente tras un match C.5.")

        if self.primary_institution_id is None:
            if self.institution_matches or not self.institution_no_exact_match_reason:
                raise ValueError("Sin institución exacta C.5 debe explicarse el no-match A.6.")
        else:
            if primary_institutions != [self.primary_institution_id]:
                raise ValueError("C.5 exige exactamente una institución primaria coherente.")
            if self.institution_no_exact_match_reason is not None:
                raise ValueError("No corresponde razón de no-match cuando existe institución C.5.")

        if not self.facts_normalized or not self.problem_institution_classified:
            raise ValueError("C.5 requiere hechos C.4 y clasificación completa.")
        if any(
            (
                self.normative_articles_linked,
                self.corpus_validated,
                self.cbr_family_assigned,
                self.operational_case_created,
                self.can_control_legal_decision,
            )
        ):
            raise ValueError("C.5 no puede adelantar C.6-C.10 ni controlar Legal Decision.")
        return self


class PrimaryCBRProblemInstitutionClassification(BaseModel):
    """Recurso C.5: clasificación de 37 candidatos contra taxonomía A.6."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    baseline_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    purpose: str = Field(min_length=20, max_length=1200)
    taxonomy_resource: str = Field(min_length=5, max_length=200)
    taxonomy_schema_version: str = Field(pattern=r"^1\.\d+$")
    taxonomy_concept_count: int = Field(ge=2)
    taxonomy_problem_count: int = Field(ge=1)
    taxonomy_institution_count: int = Field(ge=1)
    source_situation_count: int = Field(ge=1)
    classified_situation_count: int = Field(ge=1)
    primary_problem_match_count: int = Field(ge=0)
    primary_problem_no_exact_match_count: int = Field(ge=0)
    primary_institution_match_count: int = Field(ge=0)
    primary_institution_no_exact_match_count: int = Field(ge=0)
    problem_type_seed_count: int = Field(ge=0)
    problem_type_semantics: str = Field(min_length=10, max_length=300)
    classifications: list[PrimaryCBRProblemInstitutionSituation] = Field(
        min_length=1, max_length=500
    )
    creates_new_taxonomy_concepts: bool = False
    links_normative_articles: bool = False
    validates_current_law: bool = False
    assigns_cbr_families: bool = False
    creates_operational_cases: bool = False
    modifies_existing_cbr_engine: bool = False
    source_is_normative_authority: bool = False
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def validate_resource(self) -> PrimaryCBRProblemInstitutionClassification:
        if self.source_situation_count != self.classified_situation_count:
            raise ValueError("C.5 debe clasificar las 37 situaciones C.4 sin omisiones.")
        if self.classified_situation_count != len(self.classifications):
            raise ValueError("classified_situation_count no coincide con C.5.")
        ids = [item.situation_id for item in self.classifications]
        if len(ids) != len(set(ids)):
            raise ValueError("C.5 contiene situation_id duplicado.")
        if self.primary_problem_match_count != sum(
            item.primary_problem_id is not None for item in self.classifications
        ):
            raise ValueError("Conteo de problemas primarios C.5 inconsistente.")
        if self.primary_problem_no_exact_match_count != sum(
            item.primary_problem_id is None for item in self.classifications
        ):
            raise ValueError("Conteo de no-match de problema C.5 inconsistente.")
        if self.primary_institution_match_count != sum(
            item.primary_institution_id is not None for item in self.classifications
        ):
            raise ValueError("Conteo de instituciones primarias C.5 inconsistente.")
        if self.primary_institution_no_exact_match_count != sum(
            item.primary_institution_id is None for item in self.classifications
        ):
            raise ValueError("Conteo de no-match de institución C.5 inconsistente.")
        if self.problem_type_seed_count != sum(
            item.similarity_seed.problem_type is not None for item in self.classifications
        ):
            raise ValueError("Conteo de problem_type C.5 inconsistente.")
        if any(
            (
                self.creates_new_taxonomy_concepts,
                self.links_normative_articles,
                self.validates_current_law,
                self.assigns_cbr_families,
                self.creates_operational_cases,
                self.modifies_existing_cbr_engine,
                self.source_is_normative_authority,
                self.can_control_legal_decision,
            )
        ):
            raise ValueError("C.5 debe limitarse a clasificación taxonómica A.6.")
        return self
