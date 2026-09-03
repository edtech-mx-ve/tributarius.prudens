from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.primary_cbr_corpus_validation import PrimaryCBRCorpusValidationOutcome
from app.domain.primary_cbr_problem_institution import PrimaryCBRClassifiedSimilaritySeed
from app.domain.primary_legal_knowledge import PrimaryManual


class PrimaryCBRLegalSimilarityDecision(StrEnum):
    ELIGIBLE = "eligible"
    BELOW_THRESHOLD = "below_threshold"
    BLOCKED_PRIMARY_FAMILY = "blocked_primary_family"
    BLOCKED_CRITICAL_CONFLICT = "blocked_critical_conflict"
    BLOCKED_HISTORICAL_CONTEXT = "blocked_historical_context"


class PrimaryCBRLegalSimilarityProfile(BaseModel):
    """Perfil C.9 derivado de C.4-C.8, aún sin crear un CBRCase operativo."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    situation_id: str = Field(pattern=r"^(P|U)-CBR-SIT-[0-9]{3}$")
    source: PrimaryManual
    source_entry_id: str = Field(pattern=r"^(PRODECON-\d{2}|UNAM-[IVX]+)$")
    historical_regime_context: bool
    similarity_seed: PrimaryCBRClassifiedSimilaritySeed
    primary_family_id: str = Field(pattern=r"^CBR-[A-Z]+$")
    family_ids: list[str] = Field(min_length=1, max_length=12)
    concept_ids: list[str] = Field(min_length=1, max_length=12)
    corpus_validation_outcome: PrimaryCBRCorpusValidationOutcome
    corpus_validated: bool
    temporal_validation_pending: bool = True
    legal_similarity_enabled: bool = True
    operational_case_created: bool = False
    can_control_legal_decision: bool = False

    @field_validator("family_ids", "concept_ids")
    @classmethod
    def unique_values(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("C.9 no admite familias o conceptos duplicados.")
        return values

    @model_validator(mode="after")
    def validate_profile(self) -> PrimaryCBRLegalSimilarityProfile:
        if self.primary_family_id != self.family_ids[0]:
            raise ValueError("La familia primaria C.8 debe conservarse primero en C.9.")
        if not self.temporal_validation_pending or not self.legal_similarity_enabled:
            raise ValueError("C.9 habilita similitud sin cerrar todavía la validación temporal.")
        if self.operational_case_created or self.can_control_legal_decision:
            raise ValueError("C.9 no crea casos operativos ni controla Legal Decision.")
        return self


class PrimaryCBRLegalSimilarityMatch(BaseModel):
    """Vecino jurídicamente comparable de una situación primaria."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    rank: int = Field(ge=1, le=20)
    situation_id: str = Field(pattern=r"^(P|U)-CBR-SIT-[0-9]{3}$")
    source: PrimaryManual
    primary_family_id: str = Field(pattern=r"^CBR-[A-Z]+$")
    similarity: float = Field(ge=0, le=1)
    existing_cbr_field_similarity: float = Field(ge=0, le=1)
    family_overlap_similarity: float = Field(ge=0, le=1)
    taxonomy_overlap_similarity: float = Field(ge=0, le=1)
    active_existing_cbr_fields: list[str] = Field(default_factory=list, max_length=7)
    corpus_validation_outcome: PrimaryCBRCorpusValidationOutcome
    corpus_validated: bool
    historical_regime_context: bool
    requires_normative_review: bool
    requires_temporal_review: bool = True
    retrieval_eligible: bool = True
    operational_reuse_allowed: bool = False

    @model_validator(mode="after")
    def validate_match(self) -> PrimaryCBRLegalSimilarityMatch:
        if not self.requires_temporal_review:
            raise ValueError(
                "C.9 no puede cerrar la validación temporal reservada al flujo posterior."
            )
        if not self.retrieval_eligible:
            raise ValueError("El índice C.9 sólo almacena vecinos sobre el umbral.")
        if self.operational_reuse_allowed:
            raise ValueError("La reutilización operativa corresponde a C.10.")
        return self


class PrimaryCBRLegalSimilarityNeighbors(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    situation_id: str = Field(pattern=r"^(P|U)-CBR-SIT-[0-9]{3}$")
    candidate_count: int = Field(ge=0)
    returned_count: int = Field(ge=0, le=20)
    matches: list[PrimaryCBRLegalSimilarityMatch] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_counts(self) -> PrimaryCBRLegalSimilarityNeighbors:
        if self.returned_count != len(self.matches):
            raise ValueError("returned_count no coincide con los vecinos C.9.")
        if self.returned_count > self.candidate_count:
            raise ValueError("C.9 no puede devolver más vecinos que candidatos.")
        return self


class PrimaryCBRLegalSimilarityIndex(BaseModel):
    """Índice C.9 reproducible que extiende cbr.similarity sin sustituirlo."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    baseline_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    purpose: str = Field(min_length=20, max_length=1200)
    existing_similarity_module: str = "cbr.similarity"
    field_weight_source: str = "cbr.similarity.FIELD_WEIGHTS"
    minimum_similarity: float = Field(ge=0, le=1)
    top_k: int = Field(ge=1, le=20)
    profile_count: int = Field(ge=1)
    total_pair_count: int = Field(ge=0)
    same_primary_family_pair_count: int = Field(ge=0)
    blocked_primary_family_pair_count: int = Field(ge=0)
    blocked_critical_conflict_pair_count: int = Field(ge=0)
    blocked_historical_context_pair_count: int = Field(ge=0)
    below_threshold_pair_count: int = Field(ge=0)
    eligible_pair_count: int = Field(ge=0)
    stored_neighbor_link_count: int = Field(ge=0)
    component_weights: dict[str, float] = Field(min_length=3, max_length=3)
    critical_existing_fields: list[str] = Field(min_length=3, max_length=3)
    profiles: list[PrimaryCBRLegalSimilarityProfile] = Field(min_length=1)
    neighbors: list[PrimaryCBRLegalSimilarityNeighbors] = Field(min_length=1)
    extends_existing_cbr_similarity: bool = True
    replaces_existing_cbr_similarity: bool = False
    changes_existing_field_weights: bool = False
    changes_existing_retrieval_threshold: bool = False
    creates_operational_cases: bool = False
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def validate_index(self) -> PrimaryCBRLegalSimilarityIndex:
        profile_ids = [item.situation_id for item in self.profiles]
        neighbor_ids = [item.situation_id for item in self.neighbors]
        if len(profile_ids) != len(set(profile_ids)):
            raise ValueError("C.9 contiene perfiles duplicados.")
        if profile_ids != neighbor_ids:
            raise ValueError("C.9 requiere una lista de vecinos por cada perfil y mismo orden.")
        if self.profile_count != len(self.profiles):
            raise ValueError("profile_count no coincide con C.9.")
        if self.total_pair_count != self.profile_count * (self.profile_count - 1) // 2:
            raise ValueError("total_pair_count no coincide con las combinaciones C.9.")
        decisions = (
            self.blocked_primary_family_pair_count
            + self.blocked_critical_conflict_pair_count
            + self.blocked_historical_context_pair_count
            + self.below_threshold_pair_count
            + self.eligible_pair_count
        )
        if decisions != self.total_pair_count:
            raise ValueError("Los resultados de pares C.9 no cubren el universo comparado.")
        if self.same_primary_family_pair_count + self.blocked_primary_family_pair_count != (
            self.total_pair_count
        ):
            raise ValueError("La partición por familia primaria C.9 es inconsistente.")
        if self.stored_neighbor_link_count != sum(
            item.returned_count for item in self.neighbors
        ):
            raise ValueError("stored_neighbor_link_count no coincide con los vecinos C.9.")
        if set(self.component_weights) != {
            "existing_cbr_fields",
            "family_overlap",
            "taxonomy_overlap",
        }:
            raise ValueError("C.9 usa exactamente tres componentes de similitud jurídica.")
        if abs(sum(self.component_weights.values()) - 1.0) > 1e-9:
            raise ValueError("Los pesos de componentes C.9 deben sumar 1.0.")
        if not self.extends_existing_cbr_similarity or self.replaces_existing_cbr_similarity:
            raise ValueError("C.9 debe extender, nunca reemplazar, cbr.similarity.")
        if any(
            (
                self.changes_existing_field_weights,
                self.changes_existing_retrieval_threshold,
                self.creates_operational_cases,
                self.can_control_legal_decision,
            )
        ):
            raise ValueError("C.9 preserva el contrato existente y no adelanta C.10.")
        return self
