from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.primary_legal_knowledge import PrimaryManual


class PrimaryCBRNormalizedFactKind(StrEnum):
    """Forma estructural del hecho normalizado, sin clasificación jurídica C.5."""

    ACTOR = "actor"
    ROLE = "role"
    ACTIVITY = "activity"
    TAX = "tax"
    EVENT = "event"
    OBLIGATION = "obligation"
    PROCEDURE = "procedure"
    AUTHORITY_ACT = "authority_act"
    PROCEDURAL_STAGE = "procedural_stage"
    TEMPORAL = "temporal"
    AMOUNT = "amount"
    CALCULATION_COMPONENT = "calculation_component"
    ATTRIBUTE = "attribute"
    RELATIONSHIP = "relationship"


class PrimaryCBRNormalizedValueType(StrEnum):
    TEXT = "text"
    DECIMAL = "decimal"
    INTEGER = "integer"
    YEAR = "year"
    BOOLEAN = "boolean"
    PERCENTAGE = "percentage"
    RATIO = "ratio"


class PrimaryCBRNormalizationMethod(StrEnum):
    CONTROLLED_VOCABULARY = "controlled_vocabulary"
    CANONICAL_NUMERIC = "canonical_numeric"
    CANONICAL_TEMPORAL = "canonical_temporal"
    LITERAL_STRUCTURAL = "literal_structural"


class PrimaryCBRNormalizedFact(BaseModel):
    """Hecho atómico trazable hacia una afirmación fuente C.2/C.3."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    fact_id: str = Field(pattern=r"^C4-(P|U)-FCT-[0-9]{3}-[0-9]{2}$")
    raw_fact_index: int = Field(ge=1, le=30)
    source_text: str = Field(min_length=5, max_length=1500)
    kind: PrimaryCBRNormalizedFactKind
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")
    value: str = Field(min_length=1, max_length=500)
    value_type: PrimaryCBRNormalizedValueType = PrimaryCBRNormalizedValueType.TEXT
    unit: str | None = Field(default=None, max_length=40)
    method: PrimaryCBRNormalizationMethod
    source_asserted: bool = True
    legal_inference_added: bool = False

    @model_validator(mode="after")
    def validate_fact_boundary(self) -> PrimaryCBRNormalizedFact:
        if not self.source_asserted:
            raise ValueError("C.4 sólo normaliza hechos sostenidos por la fuente.")
        if self.legal_inference_added:
            raise ValueError("C.4 no puede introducir inferencias jurídicas nuevas.")
        if self.value_type in {
            PrimaryCBRNormalizedValueType.DECIMAL,
            PrimaryCBRNormalizedValueType.INTEGER,
            PrimaryCBRNormalizedValueType.PERCENTAGE,
            PrimaryCBRNormalizedValueType.RATIO,
        }:
            try:
                float(self.value)
            except ValueError as exc:
                raise ValueError("El valor numérico C.4 debe ser canónico.") from exc
        if self.value_type is PrimaryCBRNormalizedValueType.YEAR:
            year = int(self.value)
            if year < 1900 or year > 2200:
                raise ValueError("El año C.4 queda fuera del rango CBR.")
        return self


class PrimaryCBRSimilaritySeed(BaseModel):
    """Campos de hechos ya disponibles para la futura similitud CBR."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    taxpayer_type: str | None = Field(default=None, max_length=100)
    activity: str | None = Field(default=None, max_length=200)
    tax: str | None = Field(default=None, max_length=100)
    problem_type: None = None
    authority_act: str | None = Field(default=None, max_length=200)
    procedural_stage: str | None = Field(default=None, max_length=200)
    fiscal_year: int | None = Field(default=None, ge=1900, le=2200)
    evidence_fact_ids: dict[str, list[str]] = Field(default_factory=dict, max_length=7)

    @field_validator("taxpayer_type")
    @classmethod
    def canonical_taxpayer_type(cls, value: str | None) -> str | None:
        if value is not None and value not in {"individual", "legal_entity"}:
            raise ValueError("C.4 sólo usa tipos de contribuyente canónicos del CBR actual.")
        return value

    @field_validator("tax")
    @classmethod
    def canonical_tax(cls, value: str | None) -> str | None:
        if value is not None and value not in {"ISR", "IVA"}:
            raise ValueError("C.4 sólo fija ISR/IVA cuando la fuente lo identifica expresamente.")
        return value

    @model_validator(mode="after")
    def validate_seed_evidence(self) -> PrimaryCBRSimilaritySeed:
        populated = {
            "taxpayer_type": self.taxpayer_type,
            "activity": self.activity,
            "tax": self.tax,
            "authority_act": self.authority_act,
            "procedural_stage": self.procedural_stage,
            "fiscal_year": self.fiscal_year,
        }
        allowed = set(populated)
        if set(self.evidence_fact_ids) - allowed:
            raise ValueError(
                "La evidencia C.4 sólo puede apuntar a campos de similitud existentes."
            )
        for field_name, value in populated.items():
            evidence = self.evidence_fact_ids.get(field_name, [])
            if value is not None and not evidence:
                raise ValueError(f"Falta evidencia para el campo CBR {field_name}.")
            if value is None and evidence:
                raise ValueError(f"Hay evidencia para un campo CBR vacío: {field_name}.")
        return self


class PrimaryCBRNormalizedSituation(BaseModel):
    """Situación C.2/C.3 con hechos normalizados, todavía no caso CBR."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    situation_id: str = Field(pattern=r"^(P|U)-CBR-SIT-[0-9]{3}$")
    source: PrimaryManual
    source_entry_id: str = Field(pattern=r"^(PRODECON-\d{2}|UNAM-[IVX]+)$")
    historical_regime_context: bool
    raw_fact_count: int = Field(ge=1, le=30)
    normalized_fact_count: int = Field(ge=1, le=100)
    facts: list[PrimaryCBRNormalizedFact] = Field(min_length=1, max_length=100)
    similarity_seed: PrimaryCBRSimilaritySeed
    unresolved_required_case_fields: list[str] = Field(default_factory=list, max_length=5)
    raw_facts_fully_covered: bool = True
    facts_normalized: bool = True
    problem_institution_classified: bool = False
    normative_articles_linked: bool = False
    corpus_validated: bool = False
    cbr_family_assigned: bool = False
    operational_case_created: bool = False
    can_control_legal_decision: bool = False

    @field_validator("unresolved_required_case_fields")
    @classmethod
    def unique_unresolved(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("C.4 no admite campos requeridos duplicados.")
        return values

    @model_validator(mode="after")
    def validate_normalized_situation(self) -> PrimaryCBRNormalizedSituation:
        if self.normalized_fact_count != len(self.facts):
            raise ValueError("normalized_fact_count no coincide con los hechos C.4.")
        fact_ids = [fact.fact_id for fact in self.facts]
        if len(fact_ids) != len(set(fact_ids)):
            raise ValueError("C.4 contiene fact_id duplicado dentro de una situación.")
        expected_prefix = "C4-P-FCT-" if self.source is PrimaryManual.PRODECON else "C4-U-FCT-"
        if any(not fact_id.startswith(expected_prefix) for fact_id in fact_ids):
            raise ValueError("Los fact_id C.4 no corresponden con su fuente.")
        raw_indexes = (fact.raw_fact_index for fact in self.facts)
        if any(index > self.raw_fact_count for index in raw_indexes):
            raise ValueError("Un hecho C.4 referencia una afirmación fuente inexistente.")
        covered = {fact.raw_fact_index for fact in self.facts}
        if covered != set(range(1, self.raw_fact_count + 1)):
            raise ValueError("C.4 debe cubrir todas las afirmaciones fuente C.2/C.3.")
        if not self.raw_facts_fully_covered or not self.facts_normalized:
            raise ValueError("C.4 debe declarar cobertura y normalización completas.")
        if self.problem_institution_classified:
            raise ValueError("La clasificación problema/institución corresponde a C.5.")
        if self.similarity_seed.problem_type is not None:
            raise ValueError("problem_type queda reservado para C.5.")
        if any(
            (
                self.normative_articles_linked,
                self.corpus_validated,
                self.cbr_family_assigned,
                self.operational_case_created,
                self.can_control_legal_decision,
            )
        ):
            raise ValueError("C.4 no puede adelantar C.6-C.10 ni controlar Legal Decision.")
        known_fact_ids = set(fact_ids)
        for evidence_ids in self.similarity_seed.evidence_fact_ids.values():
            if not set(evidence_ids) <= known_fact_ids:
                raise ValueError("La semilla CBR referencia hechos C.4 inexistentes.")
        return self


class PrimaryCBRFactNormalization(BaseModel):
    """Recurso C.4 que normaliza hechos de PRODECON y UNAM sin decidir Derecho."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    baseline_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    purpose: str = Field(min_length=20, max_length=1200)
    prodecon_situation_count: int = Field(ge=1)
    unam_situation_count: int = Field(ge=1)
    source_situation_count: int = Field(ge=1)
    source_raw_fact_statement_count: int = Field(ge=1)
    normalized_situation_count: int = Field(ge=1)
    normalized_fact_count: int = Field(ge=1)
    similarity_fields_from_c1: list[str] = Field(min_length=1, max_length=20)
    required_case_fields: list[str] = Field(min_length=1, max_length=20)
    problem_type_deferred_to_c5: bool = True
    situations: list[PrimaryCBRNormalizedSituation] = Field(min_length=1, max_length=500)
    creates_operational_cases: bool = False
    modifies_existing_cbr_engine: bool = False
    source_is_normative_authority: bool = False
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def validate_resource(self) -> PrimaryCBRFactNormalization:
        if self.source_situation_count != self.prodecon_situation_count + self.unam_situation_count:
            raise ValueError("El total de situaciones C.4 no coincide con sus fuentes.")
        if self.normalized_situation_count != len(self.situations):
            raise ValueError("normalized_situation_count no coincide con C.4.")
        if self.normalized_situation_count != self.source_situation_count:
            raise ValueError("C.4 debe normalizar todas las situaciones C.2/C.3.")
        normalized_total = sum(
            item.normalized_fact_count for item in self.situations
        )
        if self.normalized_fact_count != normalized_total:
            raise ValueError("normalized_fact_count agregado no coincide con C.4.")
        ids = [item.situation_id for item in self.situations]
        if len(ids) != len(set(ids)):
            raise ValueError("C.4 contiene situation_id duplicado.")
        if not self.problem_type_deferred_to_c5:
            raise ValueError("C.4 debe reservar problem_type para C.5.")
        if any(
            (
                self.creates_operational_cases,
                self.modifies_existing_cbr_engine,
                self.source_is_normative_authority,
                self.can_control_legal_decision,
            )
        ):
            raise ValueError("C.4 debe preservar la frontera del CBR Primario.")
        return self
