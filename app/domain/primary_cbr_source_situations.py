from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.primary_legal_knowledge import PrimaryManual


class PrimaryCBRSituationKind(StrEnum):
    """Naturaleza de una situación fuente antes de convertirse en caso CBR."""

    CONCEPTUAL = "conceptual_situation"
    TAXPAYER = "taxpayer_situation"
    AUTHORITY = "authority_situation"
    DEFENSE = "defense_situation"
    INTERPRETATION = "interpretation_situation"
    HISTORICAL_REGIME = "historical_regime_situation"


class ExtractedPrimaryCBRSituation(BaseModel):
    """Situación extraída de una fuente primaria, todavía no operacional."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    situation_id: str = Field(pattern=r"^(P|U)-CBR-SIT-[0-9]{3}$")
    source: PrimaryManual
    source_entry_id: str = Field(pattern=r"^(PRODECON-\d{2}|UNAM-[IVX]+)$")
    source_section_order: int = Field(ge=1, le=12)
    source_section_title: str = Field(min_length=3, max_length=200)
    source_pages: list[int] = Field(min_length=1, max_length=20)
    source_locator: str = Field(min_length=5, max_length=500)
    kind: PrimaryCBRSituationKind
    source_summary: str = Field(min_length=20, max_length=1200)
    raw_fact_statements: list[str] = Field(min_length=1, max_length=30)
    historical_regime_context: bool = False
    temporal_review_required: bool = True
    requires_fact_normalization: bool = True
    requires_problem_institution_classification: bool = True
    requires_normative_article_linkage: bool = True
    requires_corpus_validation: bool = True
    eligible_for_operational_cbr: bool = False
    can_control_legal_decision: bool = False

    @field_validator("source_pages")
    @classmethod
    def unique_source_pages(cls, values: list[int]) -> list[int]:
        if len(values) != len(set(values)):
            raise ValueError("C.2 no admite páginas fuente duplicadas.")
        if values != sorted(values):
            raise ValueError("Las páginas fuente CBR deben conservar orden ascendente.")
        return values

    @field_validator("raw_fact_statements")
    @classmethod
    def unique_raw_fact_statements(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("C.2 no admite hechos fuente duplicados.")
        return values

    @model_validator(mode="after")
    def enforce_source_boundary(self) -> ExtractedPrimaryCBRSituation:
        if self.source is PrimaryManual.PRODECON:
            if not self.situation_id.startswith("P-CBR-SIT-"):
                raise ValueError("situation_id incompatible con fuente PRODECON.")
            if not self.source_entry_id.startswith("PRODECON-"):
                raise ValueError("source_entry_id incompatible con fuente PRODECON.")
        if self.source is PrimaryManual.UNAM:
            if not self.situation_id.startswith("U-CBR-SIT-"):
                raise ValueError("situation_id incompatible con fuente UNAM.")
            if not self.source_entry_id.startswith("UNAM-"):
                raise ValueError("source_entry_id incompatible con fuente UNAM.")

        required_downstream_gates = (
            self.temporal_review_required,
            self.requires_fact_normalization,
            self.requires_problem_institution_classification,
            self.requires_normative_article_linkage,
            self.requires_corpus_validation,
        )
        if not all(required_downstream_gates):
            raise ValueError(
                "C.2 debe dejar pendientes normalización, clasificación, enlace y validación."
            )
        if self.eligible_for_operational_cbr:
            raise ValueError("Una situación C.2 no puede ser todavía un caso CBR operativo.")
        if self.can_control_legal_decision:
            raise ValueError("PRODECON/UNAM no pueden controlar Legal Decision.")
        if self.kind is PrimaryCBRSituationKind.HISTORICAL_REGIME:
            if not self.historical_regime_context:
                raise ValueError(
                    "Una situación de régimen histórico debe marcar su contexto histórico."
                )
        elif self.historical_regime_context:
            raise ValueError("El contexto histórico de régimen debe usar su tipo específico.")
        return self


class PrimaryCBRSituationExtraction(BaseModel):
    """Recurso de extracción CBR previo a C.4-C.10."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    baseline_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source: PrimaryManual
    source_title: str = Field(min_length=10, max_length=300)
    purpose: str = Field(min_length=20, max_length=1200)
    source_entry_count: int = Field(ge=1, le=20)
    expected_situations_per_entry: int = Field(ge=1, le=20)
    situation_count: int = Field(ge=1, le=500)
    situations: list[ExtractedPrimaryCBRSituation] = Field(min_length=1, max_length=500)
    facts_normalized: bool = False
    problems_institutions_classified: bool = False
    normative_articles_linked: bool = False
    corpus_validated: bool = False
    cbr_families_assigned: bool = False
    operational_cases_created: bool = False
    source_is_normative_authority: bool = False
    source_can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def validate_extraction_stage(self) -> PrimaryCBRSituationExtraction:
        if self.situation_count != len(self.situations):
            raise ValueError("situation_count no coincide con la extracción CBR.")
        situation_ids = [item.situation_id for item in self.situations]
        if len(situation_ids) != len(set(situation_ids)):
            raise ValueError("La extracción CBR contiene situation_id duplicado.")
        if any(item.source is not self.source for item in self.situations):
            raise ValueError("Todas las situaciones deben pertenecer a la fuente declarada.")

        premature_stages = (
            self.facts_normalized,
            self.problems_institutions_classified,
            self.normative_articles_linked,
            self.corpus_validated,
            self.cbr_families_assigned,
            self.operational_cases_created,
        )
        if any(premature_stages):
            raise ValueError(
                "C.2/C.3 son extracción fuente y no pueden adelantar etapas posteriores."
            )
        if self.source_is_normative_authority or self.source_can_control_legal_decision:
            raise ValueError(
                "Las fuentes primarias orientan; no son autoridad normativa decisoria."
            )
        return self
