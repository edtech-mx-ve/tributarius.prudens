from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.chunks import LegalChunkType
from app.domain.normative import (
    NormativeDecision,
    NormativeValidityBasis,
    NormativeValidityScope,
    NormativeValidityStatus,
)
from app.domain.primary_cbr_corpus_validation import PrimaryCBRCorpusValidationOutcome
from app.domain.primary_cbr_levels import PrimaryCBRKnowledgeLevel
from app.domain.primary_legal_knowledge import PrimaryManual
from app.domain.primary_rbs_corpus_validation import CorpusValidationStatus
from app.domain.primary_rbs_decision_boundary import PrimaryRBSDecisionRole


class QueryIntent(StrEnum):
    UNDERSTAND_TAX_SYSTEM = "understand_tax_system"
    IDENTIFY_OBLIGATIONS = "identify_obligations"
    KNOW_RIGHTS = "know_rights"
    CALCULATE_ISR = "calculate_isr"
    CALCULATE_IVA = "calculate_iva"
    ANALYZE_AUTHORITY_ACT = "analyze_authority_act"
    REVIEW_DEBT_NONCOMPLIANCE = "review_debt_noncompliance"
    DEFENSE_OPTIONS = "defense_options"
    INTERPRET_PROVISION = "interpret_provision"
    RELATED_JURISPRUDENCE = "related_jurisprudence"
    SIMILAR_CASES = "similar_cases"
    LEARN_TAX_LAW = "learn_tax_law"
    UNKNOWN = "unknown"


class FactOrigin(StrEnum):
    EXPLICIT = "explicit"
    INFERRED = "inferred"


class ExtractedFact(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=1000)
    origin: FactOrigin = FactOrigin.EXPLICIT

    @field_validator("name", "value")
    @classmethod
    def strip_text(cls, value: str) -> str:
        clean = " ".join(value.split())
        if not clean:
            raise ValueError("El valor no puede quedar vacío.")
        return clean


class QueryEntity(BaseModel):
    entity_type: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=500)

    @field_validator("entity_type", "value")
    @classmethod
    def strip_text(cls, value: str) -> str:
        clean = " ".join(value.split())
        if not clean:
            raise ValueError("La entidad no puede quedar vacía.")
        return clean


class MissingField(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=500)


class QueryAnalysisDraft(BaseModel):
    primary_intent: QueryIntent
    secondary_intents: list[QueryIntent] = Field(default_factory=list, max_length=8)
    facts: list[ExtractedFact] = Field(default_factory=list, max_length=40)
    entities: list[QueryEntity] = Field(default_factory=list, max_length=40)
    missing_fields: list[MissingField] = Field(default_factory=list, max_length=20)
    ambiguities: list[str] = Field(default_factory=list, max_length=20)
    jurisprudence_requested: bool = False
    requires_clarification: bool = False
    requires_human_review: bool = False

    @field_validator("ambiguities")
    @classmethod
    def normalize_ambiguities(cls, values: list[str]) -> list[str]:
        return [" ".join(value.split()) for value in values if value.strip()]

    @model_validator(mode="after")
    def remove_duplicate_secondary_intent(self) -> QueryAnalysisDraft:
        self.secondary_intents = [
            intent for intent in dict.fromkeys(self.secondary_intents)
            if intent != self.primary_intent
        ]
        return self


class QueryDimensionName(StrEnum):
    TAXPAYER_TYPE = "taxpayer_type"
    ACTIVITY = "activity"
    TAX = "tax"
    FISCAL_REGIME = "fiscal_regime"
    AUTHORITY_ACT = "authority_act"
    PROCEDURAL_STAGE = "procedural_stage"
    FISCAL_YEAR = "fiscal_year"


class QueryDimensionBasis(StrEnum):
    STRUCTURED_FACT = "structured_fact"
    QUERY_TEXT = "query_text"


class QueryTaxonomyBasis(StrEnum):
    TAXONOMY_TEXT = "taxonomy_text"
    INTENT_BRIDGE = "intent_bridge"
    DIMENSION_BRIDGE = "dimension_bridge"


class QueryTaxonomyKind(StrEnum):
    PROBLEM = "problem"
    INSTITUTION = "institution"


class QueryTemporalSignalKind(StrEnum):
    EXPLICIT_YEAR = "explicit_year"
    CURRENT_CONTEXT = "current_context"
    HISTORICAL_CONTEXT = "historical_context"
    VIGENCY_REQUEST = "vigency_request"


class QueryDimensionValue(BaseModel):
    dimension: QueryDimensionName
    value: str = Field(min_length=1, max_length=300)
    origin: FactOrigin
    basis: QueryDimensionBasis
    evidence: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)


class QueryTaxonomyMatch(BaseModel):
    concept_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    kind: QueryTaxonomyKind
    label: str = Field(min_length=3, max_length=160)
    basis: QueryTaxonomyBasis
    evidence: str = Field(min_length=1, max_length=500)
    score: float = Field(ge=0, le=1)
    primary: bool = False


class QueryTemporalSignal(BaseModel):
    kind: QueryTemporalSignalKind
    value: str = Field(min_length=1, max_length=100)
    evidence: str = Field(min_length=1, max_length=500)


class MultidimensionalQueryAnalysis(BaseModel):
    """D.1: lectura estructural de la consulta, nunca determinación jurídica."""

    schema_version: str = "1.0"
    dimensions: list[QueryDimensionValue] = Field(default_factory=list, max_length=50)
    primary_problem_id: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]*$")
    primary_institution_id: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]*$")
    problem_matches: list[QueryTaxonomyMatch] = Field(default_factory=list, max_length=20)
    institution_matches: list[QueryTaxonomyMatch] = Field(default_factory=list, max_length=20)
    temporal_signals: list[QueryTemporalSignal] = Field(default_factory=list, max_length=20)
    unresolved_dimensions: list[QueryDimensionName] = Field(default_factory=list, max_length=20)
    semantic_issue_count: int = Field(default=0, ge=0, le=40)
    requires_temporal_validation: bool = False
    downstream_activation_enabled: bool = False
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def enforce_d1_boundary(self) -> MultidimensionalQueryAnalysis:
        dimension_keys = [(item.dimension, item.value.casefold()) for item in self.dimensions]
        if len(dimension_keys) != len(set(dimension_keys)):
            raise ValueError("D.1 no admite dimensiones duplicadas.")
        if len(self.unresolved_dimensions) != len(set(self.unresolved_dimensions)):
            raise ValueError("D.1 no admite dimensiones pendientes duplicadas.")
        if self.downstream_activation_enabled:
            raise ValueError("D.1 no puede activar PRODECON/UNAM, RBS, CBR ni RAG.")
        if self.can_control_legal_decision:
            raise ValueError("D.1 no puede controlar Legal Decision.")
        for matches, expected_kind in (
            (self.problem_matches, QueryTaxonomyKind.PROBLEM),
            (self.institution_matches, QueryTaxonomyKind.INSTITUTION),
        ):
            ids = [item.concept_id for item in matches]
            if len(ids) != len(set(ids)):
                raise ValueError("D.1 no admite matches taxonómicos duplicados.")
            if any(item.kind is not expected_kind for item in matches):
                raise ValueError("D.1 mezcló problemas e instituciones.")
            if sum(item.primary for item in matches) > 1:
                raise ValueError("D.1 solo admite un match primario por tipo.")
        if self.primary_problem_id is not None and not any(
            item.primary and item.concept_id == self.primary_problem_id
            for item in self.problem_matches
        ):
            raise ValueError("primary_problem_id no corresponde al match primario D.1.")
        if self.primary_institution_id is not None and not any(
            item.primary and item.concept_id == self.primary_institution_id
            for item in self.institution_matches
        ):
            raise ValueError("primary_institution_id no corresponde al match primario D.1.")
        expected_issue_count = len(self.problem_matches) + len(self.institution_matches)
        if self.semantic_issue_count != expected_issue_count:
            raise ValueError("semantic_issue_count no corresponde a los matches D.1.")
        return self


class PrimaryActivationEvidenceKind(StrEnum):
    PROBLEM = "problem"
    INSTITUTION = "institution"
    DIMENSION = "dimension"


class PrimarySourceActivationEvidence(BaseModel):
    kind: PrimaryActivationEvidenceKind
    ref: str = Field(min_length=1, max_length=200)
    contribution: float = Field(gt=0, le=1)
    detail: str = Field(min_length=1, max_length=500)


class PrimarySourceActivationEntry(BaseModel):
    entry_id: str = Field(pattern=r"^(PRODECON-\d{2}|UNAM-[IVX]+)$")
    manual: PrimaryManual
    order: int = Field(ge=1, le=12)
    title: str = Field(min_length=3, max_length=200)
    score: float = Field(ge=0, le=1)
    evidence: list[PrimarySourceActivationEvidence] = Field(min_length=1, max_length=40)
    candidate_normative_sources: list[str] = Field(default_factory=list, max_length=12)
    historical_content: bool = False
    requires_temporal_validation: bool = True
    requires_normative_validation: bool = True
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def enforce_primary_activation_entry_boundary(self) -> PrimarySourceActivationEntry:
        if len(self.candidate_normative_sources) != len(set(self.candidate_normative_sources)):
            raise ValueError("D.2 no admite fuentes normativas candidatas duplicadas.")
        if not self.requires_normative_validation:
            raise ValueError("D.2 siempre requiere validación normativa posterior.")
        if self.historical_content and not self.requires_temporal_validation:
            raise ValueError("El contenido histórico D.2 siempre requiere control temporal.")
        if self.can_control_legal_decision:
            raise ValueError("PRODECON/UNAM no pueden controlar Legal Decision.")
        return self


class PrimarySourceActivation(BaseModel):
    """D.2: activa navegación primaria sin convertir manuales en autoridad jurídica."""

    schema_version: str = "1.0"
    activation_applied: bool
    entries: list[PrimarySourceActivationEntry] = Field(default_factory=list, max_length=19)
    prodecon_count: int = Field(ge=0, le=12)
    unam_count: int = Field(ge=0, le=7)
    suppressed_entry_ids: list[str] = Field(default_factory=list, max_length=19)
    suppressed_historical_entry_ids: list[str] = Field(default_factory=list, max_length=19)
    candidate_normative_hints: list[str] = Field(default_factory=list, max_length=12)
    normative_corpus_ids: list[str] = Field(min_length=12, max_length=12)
    full_normative_corpus_preserved: bool = True
    requires_temporal_validation: bool = False
    requires_normative_validation: bool = True
    normative_ranking_enabled: bool = False
    rbs_activation_enabled: bool = False
    cbr_activation_enabled: bool = False
    rag_retrieval_enabled: bool = False
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def enforce_d2_boundary(self) -> PrimarySourceActivation:
        ids = [item.entry_id for item in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("D.2 no admite entradas primarias duplicadas.")
        if self.prodecon_count != sum(
            item.manual is PrimaryManual.PRODECON for item in self.entries
        ):
            raise ValueError("Conteo PRODECON D.2 inconsistente.")
        if self.unam_count != sum(item.manual is PrimaryManual.UNAM for item in self.entries):
            raise ValueError("Conteo UNAM D.2 inconsistente.")
        if self.activation_applied != bool(self.entries):
            raise ValueError("activation_applied no corresponde a las entradas D.2.")
        if set(self.suppressed_historical_entry_ids) - set(self.suppressed_entry_ids):
            raise ValueError("Los bloqueos históricos D.2 deben ser un subconjunto de bloqueos.")
        if len(self.normative_corpus_ids) != len(set(self.normative_corpus_ids)):
            raise ValueError("D.2 exige doce corpus normativos únicos.")
        if set(self.candidate_normative_hints) - set(self.normative_corpus_ids):
            raise ValueError("D.2 produjo una pista normativa fuera del corpus A.8.")
        if not self.full_normative_corpus_preserved:
            raise ValueError("D.2 no puede excluir fuentes normativas del espacio de búsqueda.")
        if not self.requires_normative_validation:
            raise ValueError("D.2 siempre exige validación normativa posterior.")
        if (
            self.normative_ranking_enabled
            or self.rbs_activation_enabled
            or self.cbr_activation_enabled
            or self.rag_retrieval_enabled
        ):
            raise ValueError("D.2 no puede adelantar D.3, D.4, D.5 ni D.7.")
        if self.can_control_legal_decision:
            raise ValueError("D.2 no puede controlar Legal Decision.")
        return self


class RBSOrientationEvidenceKind(StrEnum):
    PRIMARY_ENTRY = "primary_entry"
    RBS_FAMILY = "rbs_family"


class RBSOrientationEvidence(BaseModel):
    kind: RBSOrientationEvidenceKind
    ref: str = Field(min_length=1, max_length=200)
    contribution: float = Field(gt=0, le=1)
    detail: str = Field(min_length=1, max_length=500)


class RBSOrientationRelation(BaseModel):
    """D.3: relación RBS activada para orientar la investigación, no para decidir."""

    relation_id: str = Field(pattern=r"^B5-REL-[0-9]{3}$")
    label: str = Field(min_length=3, max_length=180)
    score: float = Field(ge=0, le=1)
    primary_entry_component: float = Field(ge=0, le=1)
    family_overlap_component: float = Field(ge=0, le=1)
    matched_primary_entry_ids: list[str] = Field(min_length=1, max_length=19)
    rbs_family_ids: list[str] = Field(min_length=1, max_length=17)
    matched_rbs_family_ids: list[str] = Field(default_factory=list, max_length=17)
    evidence: list[RBSOrientationEvidence] = Field(min_length=1, max_length=40)
    role: PrimaryRBSDecisionRole
    normative_source_ids: list[str] = Field(min_length=1, max_length=12)
    exact_normative_refs: list[str] = Field(default_factory=list, max_length=50)
    linked_existing_rule_ids: list[str] = Field(default_factory=list, max_length=14)
    corpus_validation_status: CorpusValidationStatus
    blocked_normative_sources: list[str] = Field(default_factory=list, max_length=12)
    corpus_membership_validated: bool = True
    temporal_applicability_confirmed: bool = False
    requires_case_date_validation: bool = True
    executable_determination_enabled: bool = False
    determination_ready: bool = False
    orientation_only: bool = True
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def enforce_d3_relation_boundary(self) -> RBSOrientationRelation:
        for values in (
            self.matched_primary_entry_ids,
            self.rbs_family_ids,
            self.matched_rbs_family_ids,
            self.normative_source_ids,
            self.exact_normative_refs,
            self.linked_existing_rule_ids,
            self.blocked_normative_sources,
        ):
            if len(values) != len(set(values)):
                raise ValueError("D.3 no admite referencias duplicadas.")
        if set(self.matched_rbs_family_ids) - set(self.rbs_family_ids):
            raise ValueError("D.3 reportó una familia coincidente fuera de la relación B.5.")
        if not self.corpus_membership_validated:
            raise ValueError("D.3 sólo orienta con relaciones B.8 presentes en el corpus.")
        if self.temporal_applicability_confirmed:
            raise ValueError("D.3 no puede confirmar aplicabilidad temporal antes de D.9.")
        if not self.requires_case_date_validation:
            raise ValueError("D.3 debe conservar validación temporal por caso.")
        if self.executable_determination_enabled or self.determination_ready:
            raise ValueError("D.3 no puede ejecutar ni declarar lista una determinación.")
        if not self.orientation_only or self.can_control_legal_decision:
            raise ValueError("D.3 es exclusivamente orientador.")
        return self


class RBSOrientationIntegration(BaseModel):
    """D.3: integración del RBS primario B.5-B.9 como navegación heurística."""

    schema_version: str = "1.0"
    activation_applied: bool
    relations: list[RBSOrientationRelation] = Field(default_factory=list, max_length=18)
    activated_relation_count: int = Field(ge=0, le=18)
    activated_rbs_family_ids: list[str] = Field(default_factory=list, max_length=17)
    linked_existing_rule_ids: list[str] = Field(default_factory=list, max_length=14)
    available_primary_relation_count: int = Field(ge=18, le=18)
    available_existing_rule_count: int = Field(ge=14, le=14)
    candidate_normative_sources: list[str] = Field(default_factory=list, max_length=12)
    normative_corpus_ids: list[str] = Field(min_length=12, max_length=12)
    full_normative_corpus_preserved: bool = True
    requires_normative_validation: bool = True
    requires_temporal_validation: bool = False
    reuse_existing_rule_engine: bool = True
    production_rule_execution_enabled: bool = False
    normative_ranking_enabled: bool = False
    cbr_activation_enabled: bool = False
    rag_retrieval_enabled: bool = False
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def enforce_d3_boundary(self) -> RBSOrientationIntegration:
        relation_ids = [item.relation_id for item in self.relations]
        if len(relation_ids) != len(set(relation_ids)):
            raise ValueError("D.3 no admite relaciones RBS duplicadas.")
        if self.activated_relation_count != len(self.relations):
            raise ValueError("Conteo de relaciones D.3 inconsistente.")
        if self.activation_applied != bool(self.relations):
            raise ValueError("activation_applied no corresponde a las relaciones D.3.")
        for values in (
            self.activated_rbs_family_ids,
            self.linked_existing_rule_ids,
            self.candidate_normative_sources,
            self.normative_corpus_ids,
        ):
            if len(values) != len(set(values)):
                raise ValueError("D.3 no admite listas agregadas duplicadas.")
        if set(self.candidate_normative_sources) - set(self.normative_corpus_ids):
            raise ValueError("D.3 produjo una pista normativa fuera del corpus A.8.")
        if not self.full_normative_corpus_preserved:
            raise ValueError("D.3 no puede excluir fuentes normativas del espacio de búsqueda.")
        if not self.requires_normative_validation or not self.reuse_existing_rule_engine:
            raise ValueError("D.3 debe conservar validación normativa y reutilizar el RBS.")
        if self.production_rule_execution_enabled:
            raise ValueError("D.3 no ejecuta reglas productivas; sólo orienta.")
        if (
            self.normative_ranking_enabled
            or self.cbr_activation_enabled
            or self.rag_retrieval_enabled
        ):
            raise ValueError("D.3 no puede adelantar D.4, D.5 ni D.7.")
        if self.can_control_legal_decision:
            raise ValueError("D.3 no puede controlar Legal Decision.")
        return self


class CBROrientationMatch(BaseModel):
    """D.4: vecino CBR primario usado sólo para orientar la investigación."""

    rank: int = Field(ge=1, le=20)
    situation_id: str = Field(pattern=r"^(P|U)-CBR-SIT-[0-9]{3}$")
    source: PrimaryManual
    source_entry_id: str = Field(pattern=r"^(PRODECON-\d{2}|UNAM-[IVX]+)$")
    primary_family_id: str = Field(pattern=r"^CBR-[A-Z]+$")
    family_ids: list[str] = Field(min_length=1, max_length=12)
    concept_ids: list[str] = Field(min_length=1, max_length=12)
    similarity: float = Field(ge=0, le=1)
    existing_cbr_field_similarity: float = Field(ge=0, le=1)
    family_overlap_similarity: float = Field(ge=0, le=1)
    taxonomy_overlap_similarity: float = Field(ge=0, le=1)
    active_existing_cbr_fields: list[str] = Field(default_factory=list, max_length=7)
    knowledge_level: PrimaryCBRKnowledgeLevel
    corpus_validation_outcome: PrimaryCBRCorpusValidationOutcome
    corpus_validated: bool
    validated_normative_refs: list[str] = Field(default_factory=list, max_length=100)
    historical_regime_context: bool
    requires_normative_review: bool
    requires_temporal_review: bool = True
    retrieval_eligible: bool = True
    operational_reuse_allowed: bool = False
    orientation_only: bool = True
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def enforce_d4_match_boundary(self) -> CBROrientationMatch:
        for values in (
            self.family_ids,
            self.concept_ids,
            self.active_existing_cbr_fields,
            self.validated_normative_refs,
        ):
            if len(values) != len(set(values)):
                raise ValueError("D.4 no admite referencias CBR duplicadas.")
        if self.primary_family_id != self.family_ids[0]:
            raise ValueError("D.4 debe conservar primero la familia CBR primaria.")
        if self.corpus_validated and self.requires_normative_review:
            raise ValueError("Un vecino validado C.7 no debe marcar revisión normativa por C.7.")
        if not self.corpus_validated and not self.requires_normative_review:
            raise ValueError("Un vecino no validado C.7 debe exigir revisión normativa.")
        if not self.requires_temporal_review:
            raise ValueError("D.4 no puede cerrar el control temporal reservado a D.9.")
        if not self.retrieval_eligible:
            raise ValueError("D.4 sólo almacena vecinos sobre el umbral C.9.")
        if self.operational_reuse_allowed:
            raise ValueError("D.4 no permite reutilización CBR operativa automática.")
        if not self.orientation_only or self.can_control_legal_decision:
            raise ValueError("D.4 es exclusivamente orientador.")
        return self


class CBROrientationIntegration(BaseModel):
    """D.4: compara la consulta con los perfiles CBR C.9 sin crear precedentes."""

    schema_version: str = "1.0"
    activation_applied: bool
    query_primary_family_id: str | None = Field(default=None, pattern=r"^CBR-[A-Z]+$")
    query_family_ids: list[str] = Field(default_factory=list, max_length=12)
    query_concept_ids: list[str] = Field(default_factory=list, max_length=12)
    query_historical_context: bool = False
    candidate_count: int = Field(ge=0, le=37)
    returned_count: int = Field(ge=0, le=20)
    matches: list[CBROrientationMatch] = Field(default_factory=list, max_length=20)
    available_primary_profile_count: int = Field(ge=37, le=37)
    available_validated_profile_count: int = Field(ge=20, le=20)
    available_operational_case_count: int = Field(ge=0, le=0)
    candidate_normative_sources: list[str] = Field(default_factory=list, max_length=12)
    normative_corpus_ids: list[str] = Field(min_length=12, max_length=12)
    full_normative_corpus_preserved: bool = True
    requires_normative_validation: bool = True
    requires_temporal_validation: bool = False
    reuse_existing_cbr_similarity: bool = True
    uses_primary_cbr_profiles: bool = True
    uses_operational_cbr_cases: bool = False
    operational_reuse_enabled: bool = False
    normative_ranking_enabled: bool = False
    rag_retrieval_enabled: bool = False
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def enforce_d4_boundary(self) -> CBROrientationIntegration:
        if self.returned_count != len(self.matches):
            raise ValueError("returned_count no coincide con los vecinos D.4.")
        if self.returned_count > self.candidate_count:
            raise ValueError("D.4 no puede devolver más vecinos que candidatos.")
        if self.activation_applied != bool(self.matches):
            raise ValueError("activation_applied no corresponde a los vecinos D.4.")
        for values in (
            self.query_family_ids,
            self.query_concept_ids,
            self.candidate_normative_sources,
            self.normative_corpus_ids,
        ):
            if len(values) != len(set(values)):
                raise ValueError("D.4 no admite listas agregadas duplicadas.")
        if self.query_primary_family_id is None and self.query_family_ids:
            raise ValueError("D.4 no puede tener familias sin familia primaria.")
        if self.query_primary_family_id is not None:
            if (
                not self.query_family_ids
                or self.query_family_ids[0] != self.query_primary_family_id
            ):
                raise ValueError("La familia primaria D.4 debe ocupar la primera posición.")
        if set(self.candidate_normative_sources) - set(self.normative_corpus_ids):
            raise ValueError("D.4 produjo una pista normativa fuera del corpus A.8.")
        if not self.full_normative_corpus_preserved:
            raise ValueError("D.4 no puede excluir fuentes normativas del espacio de búsqueda.")
        if not self.requires_normative_validation:
            raise ValueError("D.4 siempre exige validación normativa posterior.")
        if not self.reuse_existing_cbr_similarity or not self.uses_primary_cbr_profiles:
            raise ValueError("D.4 debe reutilizar la similitud C.9 y sus perfiles primarios.")
        if self.uses_operational_cbr_cases or self.operational_reuse_enabled:
            raise ValueError("D.4 no puede inventar ni reutilizar casos operativos CBR.")
        if self.normative_ranking_enabled or self.rag_retrieval_enabled:
            raise ValueError("D.4 no puede adelantar D.5 ni D.7.")
        if self.can_control_legal_decision:
            raise ValueError("D.4 no puede controlar Legal Decision.")
        return self


class NormativeRankingEvidenceKind(StrEnum):
    PRIMARY_SOURCE = "primary_source"
    RBS_ORIENTATION = "rbs_orientation"
    CBR_ORIENTATION = "cbr_orientation"


class NormativeRankingTier(StrEnum):
    FOCAL = "focal"
    SECONDARY = "secondary"
    EXPANSION = "expansion"


class NormativeRankingEvidence(BaseModel):
    kind: NormativeRankingEvidenceKind
    ref: str = Field(min_length=1, max_length=200)
    upstream_score: float = Field(ge=0, le=1)
    detail: str = Field(min_length=1, max_length=500)


class NormativeRankingSource(BaseModel):
    """D.5: prioridad de relevancia, nunca juicio de validez o jerarquía jurídica."""

    rank: int = Field(ge=1, le=12)
    corpus_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=3, max_length=300)
    relevance_score: float = Field(ge=0, le=1)
    primary_activation_component: float = Field(ge=0, le=1)
    rbs_orientation_component: float = Field(ge=0, le=1)
    cbr_orientation_component: float = Field(ge=0, le=1)
    explicit_tax_compatibility: float = Field(gt=0, le=1)
    evidence: list[NormativeRankingEvidence] = Field(default_factory=list, max_length=100)
    exact_normative_refs: list[str] = Field(default_factory=list, max_length=100)
    rbs_temporal_block_detected: bool = False
    focus_selected: bool = False
    tier: NormativeRankingTier
    canonical_order: int = Field(ge=1, le=12)
    requires_normative_validation: bool = True
    requires_temporal_validation: bool = True
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def enforce_d5_source_boundary(self) -> NormativeRankingSource:
        if len(self.exact_normative_refs) != len(set(self.exact_normative_refs)):
            raise ValueError("D.5 no admite referencias normativas exactas duplicadas.")
        if self.focus_selected != (self.tier is NormativeRankingTier.FOCAL):
            raise ValueError("La selección focal D.5 debe coincidir con el tier focal.")
        if not self.requires_normative_validation or not self.requires_temporal_validation:
            raise ValueError("D.5 no puede cerrar validación normativa ni temporal.")
        if self.can_control_legal_decision:
            raise ValueError("Una prioridad D.5 no puede controlar Legal Decision.")
        return self


class NormativeRankingIntegration(BaseModel):
    """D.5: ordena los 12 corpus A.8 por relevancia sin excluir ninguno."""

    schema_version: str = "1.0"
    ranking_applied: bool
    query_tax: str | None = Field(default=None, max_length=100)
    ranked_sources: list[NormativeRankingSource] = Field(min_length=12, max_length=12)
    focus_source_ids: list[str] = Field(default_factory=list, max_length=5)
    exact_normative_refs: list[str] = Field(default_factory=list, max_length=200)
    component_weights: dict[str, float]
    normative_corpus_ids: list[str] = Field(min_length=12, max_length=12)
    full_normative_corpus_preserved: bool = True
    source_exclusion_enabled: bool = False
    ranking_is_relevance_not_validity: bool = True
    legal_hierarchy_interpreted: bool = False
    requires_normative_validation: bool = True
    requires_temporal_validation: bool = True
    normative_validation_completed: bool = False
    temporal_validation_completed: bool = False
    structural_navigation_enabled: bool = False
    rag_retrieval_enabled: bool = False
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def enforce_d5_boundary(self) -> NormativeRankingIntegration:
        ranked_ids = [item.corpus_id for item in self.ranked_sources]
        ranks = [item.rank for item in self.ranked_sources]
        canonical_orders = [item.canonical_order for item in self.ranked_sources]
        if len(ranked_ids) != 12 or len(set(ranked_ids)) != 12:
            raise ValueError("D.5 debe ordenar exactamente 12 corpus únicos.")
        if set(ranked_ids) != set(self.normative_corpus_ids):
            raise ValueError("D.5 debe conservar exactamente el espacio normativo A.8.")
        if ranks != list(range(1, 13)):
            raise ValueError("D.5 debe asignar rangos consecutivos 1..12.")
        if sorted(canonical_orders) != list(range(1, 13)):
            raise ValueError("D.5 perdió el orden canónico A.8.")
        if len(self.normative_corpus_ids) != len(set(self.normative_corpus_ids)):
            raise ValueError("D.5 exige 12 corpus A.8 únicos.")
        if len(self.focus_source_ids) != len(set(self.focus_source_ids)):
            raise ValueError("D.5 no admite focos normativos duplicados.")
        expected_focus = [item.corpus_id for item in self.ranked_sources if item.focus_selected]
        if self.focus_source_ids != expected_focus:
            raise ValueError("focus_source_ids no corresponde al ranking D.5.")
        if len(self.exact_normative_refs) != len(set(self.exact_normative_refs)):
            raise ValueError("D.5 no admite referencias exactas agregadas duplicadas.")
        if self.ranking_applied != any(item.relevance_score > 0 for item in self.ranked_sources):
            raise ValueError("ranking_applied no corresponde a los puntajes D.5.")
        expected_weights = {"primary_activation", "rbs_orientation", "cbr_orientation"}
        if set(self.component_weights) != expected_weights:
            raise ValueError("D.5 perdió sus tres componentes de relevancia.")
        if abs(sum(self.component_weights.values()) - 1.0) > 1e-9:
            raise ValueError("Los pesos de ranking D.5 deben sumar 1.0.")
        if not self.full_normative_corpus_preserved or self.source_exclusion_enabled:
            raise ValueError("D.5 ordena; no puede excluir fuentes normativas.")
        if not self.ranking_is_relevance_not_validity or self.legal_hierarchy_interpreted:
            raise ValueError("D.5 no puede convertir relevancia en validez o jerarquía.")
        if not self.requires_normative_validation or not self.requires_temporal_validation:
            raise ValueError("D.5 siempre conserva validación normativa y temporal pendiente.")
        if self.normative_validation_completed or self.temporal_validation_completed:
            raise ValueError("D.5 no puede adelantar la validación reservada a etapas posteriores.")
        if self.structural_navigation_enabled or self.rag_retrieval_enabled:
            raise ValueError("D.5 no puede adelantar D.6 ni D.7.")
        if self.can_control_legal_decision:
            raise ValueError("D.5 no puede controlar Legal Decision.")
        return self


class StructuralNavigationLevel(StrEnum):
    TITLE = "title"
    CHAPTER = "chapter"
    SECTION = "section"
    ARTICLE = "article"


class StructuralNavigationStrategy(StrEnum):
    EXACT_ARTICLE_SEED = "exact_article_seed"
    HIERARCHY_DESCENT = "hierarchy_descent"


class StructuralNavigationTarget(BaseModel):
    """D.6: ruta estructural focal dentro de un corpus normativo priorizado."""

    rank: int = Field(ge=1, le=5)
    corpus_id: str = Field(min_length=1, max_length=100)
    source_rank: int = Field(ge=1, le=12)
    relevance_score: float = Field(ge=0, le=1)
    navigation_levels: list[StructuralNavigationLevel] = Field(min_length=4, max_length=4)
    target_level: StructuralNavigationLevel = StructuralNavigationLevel.ARTICLE
    strategy: StructuralNavigationStrategy
    exact_normative_refs: list[str] = Field(default_factory=list, max_length=100)
    article_identifiers: list[str] = Field(default_factory=list, max_length=100)
    hierarchy_scan_required: bool
    rbs_temporal_block_detected: bool = False
    requires_normative_validation: bool = True
    requires_temporal_validation: bool = True
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def enforce_d6_target_boundary(self) -> StructuralNavigationTarget:
        expected_levels = list(StructuralNavigationLevel)
        if self.navigation_levels != expected_levels:
            raise ValueError("D.6 debe conservar título/capítulo/sección/artículo en orden.")
        if self.target_level is not StructuralNavigationLevel.ARTICLE:
            raise ValueError("D.6 desciende estructuralmente hasta artículo.")
        for values in (self.exact_normative_refs, self.article_identifiers):
            if len(values) != len(set(values)):
                raise ValueError("D.6 no admite semillas estructurales duplicadas.")
        if len(self.exact_normative_refs) != len(self.article_identifiers):
            raise ValueError(
                "Cada referencia exacta D.6 debe conservar su identificador de artículo."
            )
        seeded = bool(self.exact_normative_refs)
        if seeded != (self.strategy is StructuralNavigationStrategy.EXACT_ARTICLE_SEED):
            raise ValueError("La estrategia D.6 debe corresponder a sus semillas exactas.")
        if self.hierarchy_scan_required == seeded:
            raise ValueError("D.6 sólo requiere escaneo jerárquico cuando no hay artículo exacto.")
        if not self.requires_normative_validation or not self.requires_temporal_validation:
            raise ValueError("D.6 no puede cerrar validación normativa ni temporal.")
        if self.can_control_legal_decision:
            raise ValueError("Una ruta estructural D.6 no puede controlar Legal Decision.")
        return self


class StructuralNavigationIntegration(BaseModel):
    """D.6: plan de navegación legal estructural sin recuperar todavía texto normativo."""

    schema_version: str = "1.0"
    navigation_applied: bool
    targets: list[StructuralNavigationTarget] = Field(default_factory=list, max_length=5)
    focus_source_ids: list[str] = Field(default_factory=list, max_length=5)
    hierarchy_levels: list[StructuralNavigationLevel] = Field(min_length=4, max_length=4)
    exact_normative_refs: list[str] = Field(default_factory=list, max_length=200)
    temporal_blocked_source_ids: list[str] = Field(default_factory=list, max_length=12)
    normative_corpus_ids: list[str] = Field(min_length=12, max_length=12)
    full_normative_corpus_preserved: bool = True
    source_exclusion_enabled: bool = False
    structural_navigation_enabled: bool = True
    uses_existing_chunk_hierarchy: bool = True
    normative_text_retrieved: bool = False
    requires_normative_validation: bool = True
    requires_temporal_validation: bool = True
    temporal_validation_completed: bool = False
    rag_retrieval_enabled: bool = False
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def enforce_d6_boundary(self) -> StructuralNavigationIntegration:
        expected_levels = list(StructuralNavigationLevel)
        if self.hierarchy_levels != expected_levels:
            raise ValueError("D.6 debe navegar título/capítulo/sección/artículo en orden.")
        if self.navigation_applied != bool(self.targets):
            raise ValueError("navigation_applied no corresponde a los targets D.6.")
        if [item.corpus_id for item in self.targets] != self.focus_source_ids:
            raise ValueError("Los targets D.6 deben conservar el orden focal D.5.")
        for values in (
            self.focus_source_ids,
            self.exact_normative_refs,
            self.temporal_blocked_source_ids,
            self.normative_corpus_ids,
        ):
            if len(values) != len(set(values)):
                raise ValueError("D.6 no admite listas agregadas duplicadas.")
        if len(self.normative_corpus_ids) != 12:
            raise ValueError("D.6 debe preservar exactamente los 12 corpus A.8.")
        if set(self.focus_source_ids) - set(self.normative_corpus_ids):
            raise ValueError("D.6 produjo un foco fuera del corpus A.8.")
        if set(self.temporal_blocked_source_ids) - set(self.normative_corpus_ids):
            raise ValueError("D.6 perdió un bloqueo temporal fuera del corpus A.8.")
        target_refs = [ref for item in self.targets for ref in item.exact_normative_refs]
        if self.exact_normative_refs != list(dict.fromkeys(target_refs)):
            raise ValueError("Las referencias agregadas D.6 no corresponden a sus targets.")
        if not self.full_normative_corpus_preserved or self.source_exclusion_enabled:
            raise ValueError("D.6 navega el foco sin excluir el corpus normativo completo.")
        if not self.structural_navigation_enabled or not self.uses_existing_chunk_hierarchy:
            raise ValueError("D.6 debe reutilizar la jerarquía legal ya modelada en chunks.")
        if self.normative_text_retrieved or self.rag_retrieval_enabled:
            raise ValueError("D.6 no puede adelantar la recuperación RAG D.7.")
        if not self.requires_normative_validation or not self.requires_temporal_validation:
            raise ValueError("D.6 conserva validación normativa y temporal pendiente.")
        if self.temporal_validation_completed:
            raise ValueError("D.6 no puede adelantar el control temporal D.9.")
        if self.can_control_legal_decision:
            raise ValueError("D.6 no puede controlar Legal Decision.")
        return self


class FocusedRAGRetrievalMode(StrEnum):
    EXACT_ARTICLE = "exact_article"
    FOCUSED_SEMANTIC = "focused_semantic"


class FocusedRAGTarget(BaseModel):
    """D.7: objetivo normativo acotado derivado de una ruta D.6."""

    rank: int = Field(ge=1, le=5)
    corpus_id: str = Field(min_length=1, max_length=100)
    source_rank: int = Field(ge=1, le=12)
    source_relevance_score: float = Field(ge=0, le=1)
    retrieval_modes: list[FocusedRAGRetrievalMode] = Field(min_length=1, max_length=2)
    exact_normative_refs: list[str] = Field(default_factory=list, max_length=100)
    article_identifiers: list[str] = Field(default_factory=list, max_length=100)
    requires_normative_validation: bool = True
    requires_temporal_validation: bool = True
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def enforce_d7_target_boundary(self) -> FocusedRAGTarget:
        if len(self.retrieval_modes) != len(set(self.retrieval_modes)):
            raise ValueError("D.7 no admite modos de recuperación duplicados.")
        if len(self.exact_normative_refs) != len(set(self.exact_normative_refs)):
            raise ValueError("D.7 no admite referencias exactas duplicadas.")
        if len(self.article_identifiers) != len(set(self.article_identifiers)):
            raise ValueError("D.7 no admite identificadores de artículo duplicados.")
        if len(self.exact_normative_refs) != len(self.article_identifiers):
            raise ValueError("D.7 debe conservar una referencia por identificador de artículo.")
        has_exact = bool(self.exact_normative_refs)
        if has_exact != (FocusedRAGRetrievalMode.EXACT_ARTICLE in self.retrieval_modes):
            raise ValueError("El modo exacto D.7 debe corresponder a las semillas D.6.")
        if FocusedRAGRetrievalMode.FOCUSED_SEMANTIC not in self.retrieval_modes:
            raise ValueError("Todo objetivo D.7 conserva recuperación semántica focal.")
        if not self.requires_normative_validation or not self.requires_temporal_validation:
            raise ValueError("D.7 no puede cerrar validación normativa ni temporal.")
        if self.can_control_legal_decision:
            raise ValueError("Un objetivo RAG D.7 no puede controlar Legal Decision.")
        return self


class FocusedRAGPlan(BaseModel):
    """D.7: plan de recuperación normativa focal; D.8 conserva la expansión posterior."""

    schema_version: str = "1.0"
    plan_applied: bool
    targets: list[FocusedRAGTarget] = Field(default_factory=list, max_length=5)
    focus_source_ids: list[str] = Field(default_factory=list, max_length=5)
    exact_normative_refs: list[str] = Field(default_factory=list, max_length=200)
    temporal_blocked_source_ids: list[str] = Field(default_factory=list, max_length=12)
    normative_corpus_ids: list[str] = Field(min_length=12, max_length=12)
    allowed_chunk_types: list[LegalChunkType] = Field(min_length=5, max_length=5)
    normative_only: bool = True
    full_normative_corpus_preserved: bool = True
    source_exclusion_enabled: bool = False
    structural_navigation_consumed: bool = True
    rag_retrieval_enabled: bool
    normative_text_retrieved: bool = False
    expansion_to_full_corpus_enabled: bool = False
    expansion_pending: bool = True
    requires_normative_validation: bool = True
    requires_temporal_validation: bool = True
    temporal_validation_completed: bool = False
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def enforce_d7_plan_boundary(self) -> FocusedRAGPlan:
        if self.plan_applied != bool(self.targets):
            raise ValueError("plan_applied no corresponde a los targets D.7.")
        if self.rag_retrieval_enabled != self.plan_applied:
            raise ValueError("D.7 sólo habilita RAG cuando existe un foco estructural.")
        if [item.corpus_id for item in self.targets] != self.focus_source_ids:
            raise ValueError("Los targets D.7 deben conservar el orden focal D.6.")
        for values in (
            self.focus_source_ids,
            self.exact_normative_refs,
            self.temporal_blocked_source_ids,
            self.normative_corpus_ids,
        ):
            if len(values) != len(set(values)):
                raise ValueError("D.7 no admite listas agregadas duplicadas.")
        if len(self.normative_corpus_ids) != 12:
            raise ValueError("D.7 debe preservar exactamente los 12 corpus A.8.")
        if set(self.focus_source_ids) - set(self.normative_corpus_ids):
            raise ValueError("D.7 produjo un foco fuera del corpus A.8.")
        if set(self.temporal_blocked_source_ids) - set(self.normative_corpus_ids):
            raise ValueError("D.7 perdió un bloqueo temporal fuera del corpus A.8.")
        target_refs = [ref for item in self.targets for ref in item.exact_normative_refs]
        if self.exact_normative_refs != list(dict.fromkeys(target_refs)):
            raise ValueError("Las referencias agregadas D.7 no corresponden a sus targets.")
        expected_types = {
            LegalChunkType.ARTICLE,
            LegalChunkType.SECTION,
            LegalChunkType.FRACTION,
            LegalChunkType.SUBSECTION,
            LegalChunkType.PARAGRAPH,
        }
        if set(self.allowed_chunk_types) != expected_types:
            raise ValueError("D.7 debe recuperar unidades normativas materiales compatibles.")
        if not self.normative_only:
            raise ValueError("D.7 focalizado sólo recupera evidencia normativa interna.")
        if not self.full_normative_corpus_preserved or self.source_exclusion_enabled:
            raise ValueError("D.7 focaliza sin excluir el espacio normativo completo.")
        if not self.structural_navigation_consumed:
            raise ValueError("D.7 debe consumir la navegación estructural D.6.")
        if self.normative_text_retrieved:
            raise ValueError("El plan D.7 no puede afirmar texto recuperado antes de ejecutarse.")
        if self.expansion_to_full_corpus_enabled or not self.expansion_pending:
            raise ValueError("La expansión al corpus completo queda reservada a D.8.")
        if not self.requires_normative_validation or not self.requires_temporal_validation:
            raise ValueError("D.7 conserva validación normativa y temporal pendiente.")
        if self.temporal_validation_completed:
            raise ValueError("D.7 no puede adelantar el control temporal D.9.")
        if self.can_control_legal_decision:
            raise ValueError("D.7 no puede controlar Legal Decision.")
        return self


class FocusedRAGExecution(BaseModel):
    """D.7: trazabilidad de la ejecución focal sin convertir hits en norma aplicable."""

    schema_version: str = "1.0"
    retrieval_applied: bool
    requested_top_k: int = Field(ge=1, le=20)
    candidate_count: int = Field(ge=0)
    returned_count: int = Field(ge=0, le=20)
    focus_source_ids: list[str] = Field(default_factory=list, max_length=5)
    hit_chunk_ids: list[str] = Field(default_factory=list, max_length=20)
    hit_source_ids: list[str] = Field(default_factory=list, max_length=5)
    exact_seed_hit_ids: list[str] = Field(default_factory=list, max_length=20)
    rejected_non_normative_hits: int = Field(default=0, ge=0)
    rejected_outside_focus_hits: int = Field(default=0, ge=0)
    normative_only: bool = True
    focus_scope_enforced: bool = True
    normative_text_retrieved: bool
    full_normative_corpus_preserved: bool = True
    expansion_pending: bool = True
    requires_normative_validation: bool = True
    requires_temporal_validation: bool = True
    temporal_validation_completed: bool = False
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def enforce_d7_execution_boundary(self) -> FocusedRAGExecution:
        if self.returned_count != len(self.hit_chunk_ids):
            raise ValueError("returned_count no corresponde a los hits D.7.")
        if self.normative_text_retrieved != bool(self.hit_chunk_ids):
            raise ValueError("normative_text_retrieved no corresponde a la ejecución D.7.")
        for values in (
            self.focus_source_ids,
            self.hit_chunk_ids,
            self.hit_source_ids,
            self.exact_seed_hit_ids,
        ):
            if len(values) != len(set(values)):
                raise ValueError("D.7 no admite identificadores de ejecución duplicados.")
        if set(self.hit_source_ids) - set(self.focus_source_ids):
            raise ValueError("D.7 devolvió una fuente fuera del foco.")
        if set(self.exact_seed_hit_ids) - set(self.hit_chunk_ids):
            raise ValueError("Los hits exactos D.7 deben pertenecer a los hits devueltos.")
        if not self.normative_only or not self.focus_scope_enforced:
            raise ValueError("D.7 debe imponer fuente normativa y foco estructural.")
        if not self.full_normative_corpus_preserved or not self.expansion_pending:
            raise ValueError("D.7 debe dejar disponible la expansión D.8.")
        if not self.requires_normative_validation or not self.requires_temporal_validation:
            raise ValueError("D.7 no puede cerrar validación normativa ni temporal.")
        if self.temporal_validation_completed or self.can_control_legal_decision:
            raise ValueError("D.7 no puede adelantar D.9 ni controlar Legal Decision.")
        return self


class FullCorpusExpansionReason(StrEnum):
    NO_FOCUSED_PLAN = "no_focused_plan"
    NO_FOCUSED_HITS = "no_focused_hits"
    INSUFFICIENT_FOCUSED_HITS = "insufficient_focused_hits"
    INSUFFICIENT_FOCUSED_SOURCE_COVERAGE = "insufficient_focused_source_coverage"
    MULTI_ISSUE_QUERY = "multi_issue_query"
    TEMPORAL_BLOCK_PRESENT = "temporal_block_present"


class FullCorpusExpansionPlan(BaseModel):
    """D.8: política de expansión que preserva el foco y habilita los 12 corpus A.8."""

    schema_version: str = "1.0"
    plan_applied: bool = True
    focus_source_ids: list[str] = Field(default_factory=list, max_length=5)
    expansion_source_ids: list[str] = Field(min_length=7, max_length=12)
    normative_corpus_ids: list[str] = Field(min_length=12, max_length=12)
    source_relevance_scores: dict[str, float]
    allowed_chunk_types: list[LegalChunkType] = Field(min_length=5, max_length=5)
    semantic_issue_count: int = Field(default=0, ge=0, le=100)
    temporal_blocked_source_ids: list[str] = Field(default_factory=list, max_length=12)
    minimum_focused_hits: int = Field(ge=1, le=20)
    minimum_focused_source_count: int = Field(ge=1, le=5)
    full_corpus_fallback_enabled: bool = True
    expansion_after_focused_insufficiency: bool = True
    trigger_on_multi_issue: bool = True
    trigger_on_temporal_block: bool = True
    normative_only: bool = True
    focused_priority_preserved: bool = True
    expansion_to_full_corpus_enabled: bool = True
    full_normative_corpus_preserved: bool = True
    source_exclusion_enabled: bool = False
    requires_normative_validation: bool = True
    requires_temporal_validation: bool = True
    temporal_validation_completed: bool = False
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def enforce_d8_plan_boundary(self) -> FullCorpusExpansionPlan:
        if not self.plan_applied:
            raise ValueError("D.8 debe formalizar siempre una decisión de expansión.")
        for values in (
            self.focus_source_ids,
            self.expansion_source_ids,
            self.normative_corpus_ids,
            self.temporal_blocked_source_ids,
        ):
            if len(values) != len(set(values)):
                raise ValueError("D.8 no admite identificadores de corpus duplicados.")
        if len(self.normative_corpus_ids) != 12:
            raise ValueError("D.8 debe preservar exactamente los 12 corpus A.8.")
        corpus = set(self.normative_corpus_ids)
        if set(self.focus_source_ids) - corpus:
            raise ValueError("D.8 recibió un foco fuera del corpus A.8.")
        if set(self.expansion_source_ids) - corpus:
            raise ValueError("D.8 produjo una expansión fuera del corpus A.8.")
        if set(self.focus_source_ids) & set(self.expansion_source_ids):
            raise ValueError("D.8 debe expandir únicamente fuera del foco ya consultado.")
        if set(self.focus_source_ids) | set(self.expansion_source_ids) != corpus:
            raise ValueError("Foco y expansión D.8 deben cubrir conjuntamente los 12 corpus.")
        if set(self.temporal_blocked_source_ids) - corpus:
            raise ValueError("D.8 perdió un bloqueo temporal fuera del corpus A.8.")
        if set(self.source_relevance_scores) != corpus:
            raise ValueError("D.8 requiere un score de relevancia para los 12 corpus.")
        if any(score < 0 or score > 1 for score in self.source_relevance_scores.values()):
            raise ValueError("Los scores D.8 deben permanecer entre 0 y 1.")
        expected_types = {
            LegalChunkType.ARTICLE,
            LegalChunkType.SECTION,
            LegalChunkType.FRACTION,
            LegalChunkType.SUBSECTION,
            LegalChunkType.PARAGRAPH,
        }
        if set(self.allowed_chunk_types) != expected_types:
            raise ValueError("D.8 debe conservar los tipos materiales de chunk D.7.")
        if not self.full_corpus_fallback_enabled:
            raise ValueError("D.8 debe cubrir consultas sin foco mediante fallback normativo.")
        if not self.expansion_after_focused_insufficiency:
            raise ValueError("D.8 debe poder ampliar un foco insuficiente.")
        if not self.normative_only or not self.focused_priority_preserved:
            raise ValueError("D.8 debe ser normativo y preservar prioridad focal.")
        if not self.expansion_to_full_corpus_enabled:
            raise ValueError("D.8 debe habilitar expansión al corpus normativo completo.")
        if not self.full_normative_corpus_preserved or self.source_exclusion_enabled:
            raise ValueError("D.8 no puede excluir fuentes normativas del espacio A.8.")
        if not self.requires_normative_validation or not self.requires_temporal_validation:
            raise ValueError("D.8 no reemplaza validación normativa ni temporal.")
        if self.temporal_validation_completed or self.can_control_legal_decision:
            raise ValueError("D.8 no puede adelantar D.9 ni controlar Legal Decision.")
        return self


class FullCorpusExpansionExecution(BaseModel):
    """D.8: decisión y trazabilidad de la expansión sin declarar aplicabilidad jurídica."""

    schema_version: str = "1.0"
    decision_completed: bool = True
    expansion_applied: bool
    trigger_reasons: list[FullCorpusExpansionReason] = Field(default_factory=list, max_length=6)
    requested_top_k: int = Field(ge=1, le=20)
    candidate_count: int = Field(ge=0)
    returned_count: int = Field(ge=0, le=20)
    focus_source_ids: list[str] = Field(default_factory=list, max_length=5)
    searched_expansion_source_ids: list[str] = Field(default_factory=list, max_length=12)
    combined_searched_source_ids: list[str] = Field(default_factory=list, max_length=12)
    focused_hit_chunk_ids: list[str] = Field(default_factory=list, max_length=20)
    expansion_hit_chunk_ids: list[str] = Field(default_factory=list, max_length=20)
    merged_hit_chunk_ids: list[str] = Field(default_factory=list, max_length=20)
    hit_source_ids: list[str] = Field(default_factory=list, max_length=12)
    rejected_non_normative_hits: int = Field(default=0, ge=0)
    rejected_outside_corpus_hits: int = Field(default=0, ge=0)
    normative_only: bool = True
    focused_priority_preserved: bool = True
    normative_text_retrieved: bool
    full_corpus_search_coverage_complete: bool
    full_normative_corpus_preserved: bool = True
    source_exclusion_enabled: bool = False
    requires_normative_validation: bool = True
    requires_temporal_validation: bool = True
    temporal_validation_completed: bool = False
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def enforce_d8_execution_boundary(self) -> FullCorpusExpansionExecution:
        if not self.decision_completed:
            raise ValueError("D.8 debe registrar siempre una decisión completa de expansión.")
        if self.returned_count != len(self.merged_hit_chunk_ids):
            raise ValueError("returned_count no corresponde a los hits fusionados D.8.")
        if self.normative_text_retrieved != bool(self.merged_hit_chunk_ids):
            raise ValueError("normative_text_retrieved no corresponde a la ejecución D.8.")
        for values in (
            self.trigger_reasons,
            self.focus_source_ids,
            self.searched_expansion_source_ids,
            self.combined_searched_source_ids,
            self.focused_hit_chunk_ids,
            self.expansion_hit_chunk_ids,
            self.merged_hit_chunk_ids,
            self.hit_source_ids,
        ):
            if len(values) != len(set(values)):
                raise ValueError("D.8 no admite identificadores o razones duplicadas.")
        if self.expansion_applied != bool(self.trigger_reasons):
            raise ValueError("La aplicación D.8 debe corresponder a sus razones de expansión.")
        if not self.expansion_applied and self.searched_expansion_source_ids:
            raise ValueError("D.8 no puede reportar fuentes expandidas si no se ejecutó expansión.")
        if set(self.expansion_hit_chunk_ids) - set(self.merged_hit_chunk_ids):
            raise ValueError("Los hits de expansión D.8 deben pertenecer al resultado fusionado.")
        if set(self.focused_hit_chunk_ids) - set(self.merged_hit_chunk_ids):
            raise ValueError("Los hits focales retenidos deben pertenecer al resultado fusionado.")
        if not self.normative_only or not self.focused_priority_preserved:
            raise ValueError("D.8 debe preservar evidencia normativa y prioridad focal.")
        if not self.full_normative_corpus_preserved or self.source_exclusion_enabled:
            raise ValueError("D.8 no puede excluir el corpus normativo A.8.")
        if not self.requires_normative_validation or not self.requires_temporal_validation:
            raise ValueError("D.8 conserva validación normativa y temporal pendiente.")
        if self.temporal_validation_completed or self.can_control_legal_decision:
            raise ValueError("D.8 no puede adelantar D.9 ni controlar Legal Decision.")
        return self


class TemporalYearResolution(StrEnum):
    REQUEST_FISCAL_YEAR = "request_fiscal_year"
    QUERY_EXPLICIT_YEAR = "query_explicit_year"
    QUERY_DATE_ONLY = "query_date_only"
    AMBIGUOUS_QUERY_YEARS = "ambiguous_query_years"
    CONFLICT = "conflict"


class TemporalControlPlan(BaseModel):
    """D.9: política temporal fail-closed; la ejecución ocurre tras recuperar norma."""

    schema_version: str = "1.0"
    plan_applied: bool = True
    explicit_query_years: list[int] = Field(default_factory=list, max_length=20)
    historical_context: bool = False
    current_context: bool = False
    vigency_requested: bool = False
    temporal_blocked_source_ids: list[str] = Field(default_factory=list, max_length=12)
    normative_corpus_ids: list[str] = Field(min_length=12, max_length=12)
    infer_single_explicit_year_as_fiscal_year: bool = True
    fail_closed_unknown_validity: bool = True
    fail_closed_query_year_conflict: bool = True
    fail_closed_query_year_ambiguity: bool = True
    preserve_retrieved_normative_evidence: bool = True
    rule_promotion_requires_temporal_applicability: bool = True
    temporal_control_enabled: bool = True
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def enforce_d9_plan_boundary(self) -> TemporalControlPlan:
        if not self.plan_applied or not self.temporal_control_enabled:
            raise ValueError("D.9 debe formalizar y habilitar siempre el control temporal.")
        if len(self.explicit_query_years) != len(set(self.explicit_query_years)):
            raise ValueError("D.9 no admite años explícitos duplicados.")
        if any(year < 1900 or year > 2200 for year in self.explicit_query_years):
            raise ValueError("D.9 recibió años explícitos fuera de rango.")
        if len(self.normative_corpus_ids) != 12:
            raise ValueError("D.9 debe preservar exactamente los 12 corpus A.8.")
        if len(self.normative_corpus_ids) != len(set(self.normative_corpus_ids)):
            raise ValueError("D.9 exige 12 corpus A.8 únicos.")
        if len(self.temporal_blocked_source_ids) != len(
            set(self.temporal_blocked_source_ids)
        ):
            raise ValueError("D.9 no admite bloqueos temporales duplicados.")
        if set(self.temporal_blocked_source_ids) - set(self.normative_corpus_ids):
            raise ValueError("D.9 recibió un bloqueo fuera del corpus A.8.")
        if not self.infer_single_explicit_year_as_fiscal_year:
            raise ValueError("D.9 debe consumir un único año explícito sin inventar fechas.")
        if not self.fail_closed_unknown_validity:
            raise ValueError("D.9 debe fallar cerrado ante vigencia desconocida.")
        if not self.fail_closed_query_year_conflict:
            raise ValueError("D.9 debe fallar cerrado ante conflicto de ejercicio.")
        if not self.fail_closed_query_year_ambiguity:
            raise ValueError("D.9 debe fallar cerrado ante ambigüedad de ejercicio.")
        if not self.preserve_retrieved_normative_evidence:
            raise ValueError("D.9 no puede borrar evidencia normativa recuperada.")
        if not self.rule_promotion_requires_temporal_applicability:
            raise ValueError("D.9 debe exigir aplicabilidad antes de promover al RBS.")
        if self.can_control_legal_decision:
            raise ValueError("D.9 controla promoción temporal, no Legal Decision.")
        return self


class TemporalControlCandidateResult(BaseModel):
    """D.9: resultado temporal por candidato, preservando evidencia no aplicable."""

    ref: str = Field(min_length=1, max_length=300)
    document_id: str | None = Field(default=None, max_length=200)
    decision: NormativeDecision
    applicable_by_normative_engine: bool
    promoted_for_reasoning: bool
    evidence_preserved: bool
    temporal_guard_document_blocked: bool = False
    validity_status: NormativeValidityStatus
    validity_scope: NormativeValidityScope
    validity_basis: NormativeValidityBasis
    effective_from: date | None = None
    effective_to: date | None = None
    fiscal_year: int | None = Field(default=None, ge=1900, le=2200)
    requires_human_review: bool = False

    @model_validator(mode="after")
    def enforce_d9_candidate_boundary(self) -> TemporalControlCandidateResult:
        if self.promoted_for_reasoning and not self.applicable_by_normative_engine:
            raise ValueError("D.9 no puede promover un candidato temporalmente no aplicable.")
        if self.promoted_for_reasoning and not self.evidence_preserved:
            raise ValueError("D.9 sólo promueve evidencia normativa conservada.")
        if self.decision is NormativeDecision.UNKNOWN_VALIDITY and self.promoted_for_reasoning:
            raise ValueError("unknown_validity debe permanecer fail-closed en D.9.")
        return self


class TemporalControlExecution(BaseModel):
    """D.9: ejecución temporal trazable; decide promoción, no la conclusión jurídica."""

    schema_version: str = "1.0"
    control_completed: bool = True
    query_date: date
    requested_query_fiscal_year: int | None = Field(default=None, ge=1900, le=2200)
    resolved_query_fiscal_year: int | None = Field(default=None, ge=1900, le=2200)
    year_resolution: TemporalYearResolution
    explicit_query_years: list[int] = Field(default_factory=list, max_length=20)
    query_temporal_conflict: bool = False
    query_temporal_ambiguity: bool = False
    candidate_count: int = Field(ge=0, le=100)
    applicable_count: int = Field(ge=0, le=100)
    promoted_count: int = Field(ge=0, le=100)
    evidence_refs: list[str] = Field(default_factory=list, max_length=100)
    promoted_normative_refs: list[str] = Field(default_factory=list, max_length=100)
    unknown_validity_refs: list[str] = Field(default_factory=list, max_length=100)
    expired_refs: list[str] = Field(default_factory=list, max_length=100)
    not_yet_effective_refs: list[str] = Field(default_factory=list, max_length=100)
    fiscal_year_mismatch_refs: list[str] = Field(default_factory=list, max_length=100)
    invalid_data_refs: list[str] = Field(default_factory=list, max_length=100)
    temporal_blocked_source_ids: list[str] = Field(default_factory=list, max_length=12)
    blocked_source_ids_in_retrieval: list[str] = Field(default_factory=list, max_length=12)
    candidate_results: list[TemporalControlCandidateResult] = Field(
        default_factory=list,
        max_length=100,
    )
    fail_closed_enforced: bool = True
    retrieved_evidence_preserved: bool = True
    rule_promotion_restricted_to_temporally_applicable: bool = True
    temporal_validation_completed: bool = True
    all_temporal_questions_resolved: bool
    requires_human_review: bool = False
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def enforce_d9_execution_boundary(self) -> TemporalControlExecution:
        if not self.control_completed or not self.temporal_validation_completed:
            raise ValueError("D.9 debe registrar una ejecución temporal completa.")
        if self.candidate_count != len(self.candidate_results):
            raise ValueError("candidate_count no corresponde a los resultados D.9.")
        if self.applicable_count != sum(
            item.applicable_by_normative_engine for item in self.candidate_results
        ):
            raise ValueError("applicable_count D.9 es inconsistente.")
        if self.promoted_count != len(self.promoted_normative_refs):
            raise ValueError("promoted_count D.9 es inconsistente.")
        expected_promoted = [
            item.ref for item in self.candidate_results if item.promoted_for_reasoning
        ]
        if self.promoted_normative_refs != expected_promoted:
            raise ValueError("Las referencias promovidas no corresponden a D.9.")
        for values in (
            self.explicit_query_years,
            self.evidence_refs,
            self.promoted_normative_refs,
            self.unknown_validity_refs,
            self.expired_refs,
            self.not_yet_effective_refs,
            self.fiscal_year_mismatch_refs,
            self.invalid_data_refs,
            self.temporal_blocked_source_ids,
            self.blocked_source_ids_in_retrieval,
        ):
            if len(values) != len(set(values)):
                raise ValueError("D.9 no admite listas de control temporal duplicadas.")
        if set(self.promoted_normative_refs) - set(self.evidence_refs):
            raise ValueError("D.9 no puede promover refs fuera de la evidencia preservada.")
        if set(self.unknown_validity_refs) & set(self.promoted_normative_refs):
            raise ValueError("D.9 debe bloquear unknown_validity antes del razonamiento.")
        if (self.query_temporal_conflict or self.query_temporal_ambiguity) and (
            self.promoted_normative_refs
        ):
            raise ValueError("D.9 debe bloquear promoción ante conflicto o ambigüedad temporal.")
        if not self.fail_closed_enforced or not self.retrieved_evidence_preserved:
            raise ValueError("D.9 debe ser fail-closed y conservar evidencia recuperada.")
        if not self.rule_promotion_restricted_to_temporally_applicable:
            raise ValueError("D.9 debe restringir la promoción normativa al RBS.")
        if self.can_control_legal_decision:
            raise ValueError("D.9 no puede controlar Legal Decision.")
        return self


class QueryAnalysis(BaseModel):
    original_query: str = Field(min_length=1, max_length=4000)
    normalized_query: str = Field(min_length=1, max_length=4000)
    primary_intent: QueryIntent
    secondary_intents: list[QueryIntent] = Field(default_factory=list)
    facts: list[ExtractedFact] = Field(default_factory=list)
    entities: list[QueryEntity] = Field(default_factory=list)
    missing_fields: list[MissingField] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    jurisprudence_requested: bool = False
    requires_clarification: bool = False
    requires_human_review: bool = False
    multidimensional: MultidimensionalQueryAnalysis | None = None
    primary_source_activation: PrimarySourceActivation | None = None
    rbs_orientation: RBSOrientationIntegration | None = None
    cbr_orientation: CBROrientationIntegration | None = None
    normative_ranking: NormativeRankingIntegration | None = None
    structural_navigation: StructuralNavigationIntegration | None = None
    focused_rag_plan: FocusedRAGPlan | None = None
    full_corpus_expansion_plan: FullCorpusExpansionPlan | None = None
    temporal_control_plan: TemporalControlPlan | None = None
