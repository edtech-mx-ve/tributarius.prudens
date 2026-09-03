from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.primary_legal_knowledge import PrimaryManual


class PrimaryCBRCorpusArticleState(StrEnum):
    """Estado observado del artículo en el snapshot normativo interno usado por C.7."""

    ACTIVE = "active"
    DEROGATED = "derogated"
    CONTENT_MISMATCH = "content_mismatch"


class PrimaryCBRCorpusValidationOutcome(StrEnum):
    """Resultado jurídico-técnico C.7 sin presumir vigencia para un caso concreto."""

    CONSISTENT = "consistent"
    BLOCKED_DEROGATED = "blocked_derogated"
    BLOCKED_CONTENT_MISMATCH = "blocked_content_mismatch"
    NO_EXPLICIT_CITATION = "no_explicit_citation"


class PrimaryCBRNormativeCorpusSnapshot(BaseModel):
    """Fuente normativa primaria usada para verificar referencias C.6."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    canonical_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    filename: str = Field(min_length=3, max_length=200)
    title: str = Field(min_length=3, max_length=300)
    last_reform_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    present_in_primary_manifest: bool = True
    present_in_fiscal_catalog: bool = True
    normative_layer_confirmed: bool = True
    evidence_basis: str = Field(min_length=10, max_length=300)

    @model_validator(mode="after")
    def validate_snapshot(self) -> PrimaryCBRNormativeCorpusSnapshot:
        if not (
            self.present_in_primary_manifest
            and self.present_in_fiscal_catalog
            and self.normative_layer_confirmed
        ):
            raise ValueError("C.7 sólo puede verificar contra corpus normativo interno A.8.")
        return self


class PrimaryCBRArticleCorpusValidation(BaseModel):
    """Verificación de un vínculo C.6 contra el corpus normativo primario."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    link_id: str = Field(pattern=r"^C6-(P|U)-LNK-[0-9]{3}-[0-9]{2}$")
    candidate_normative_ref: str = Field(
        pattern=r"^[a-z][a-z0-9_]*:articulo_[0-9]+(?:_[a-z])?$"
    )
    candidate_corpus_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    article: str = Field(pattern=r"^[0-9]+(?:-[A-Za-z])?$")
    qualifier: str | None = Field(default=None, min_length=2, max_length=200)
    corpus_filename: str = Field(min_length=3, max_length=200)
    article_presence_verified: bool = True
    article_state: PrimaryCBRCorpusArticleState
    source_claim_supported_by_current_article: bool
    document_wide_temporal_block: bool
    temporal_validity_confirmed: bool = False
    requires_case_date_validation: bool = True
    current_law_verified: bool = False
    validation_outcome: PrimaryCBRCorpusValidationOutcome
    verification_note: str = Field(min_length=15, max_length=700)
    external_legal_evidence_used: bool = False
    can_support_current_determination: bool = False
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def validate_article_result(self) -> PrimaryCBRArticleCorpusValidation:
        expected_article = self.article.lower().replace("-", "_")
        expected_ref = f"{self.candidate_corpus_id}:articulo_{expected_article}"
        if self.candidate_normative_ref != expected_ref:
            raise ValueError("C.7 altera la referencia normativa candidata de C.6.")
        if not self.article_presence_verified:
            raise ValueError(
                "El dataset C.7 sólo registra artículos cuya presencia fue comprobada."
            )
        expected_outcome = {
            PrimaryCBRCorpusArticleState.ACTIVE: PrimaryCBRCorpusValidationOutcome.CONSISTENT,
            PrimaryCBRCorpusArticleState.DEROGATED: (
                PrimaryCBRCorpusValidationOutcome.BLOCKED_DEROGATED
            ),
            PrimaryCBRCorpusArticleState.CONTENT_MISMATCH: (
                PrimaryCBRCorpusValidationOutcome.BLOCKED_CONTENT_MISMATCH
            ),
        }[self.article_state]
        if self.validation_outcome != expected_outcome:
            raise ValueError("Estado y resultado C.7 son incompatibles.")
        expected_supported = self.article_state == PrimaryCBRCorpusArticleState.ACTIVE
        if self.source_claim_supported_by_current_article != expected_supported:
            raise ValueError("El soporte material C.7 no coincide con el estado del artículo.")
        if self.temporal_validity_confirmed or self.current_law_verified:
            raise ValueError("C.7 no sustituye la validación temporal por fecha de caso.")
        if not self.requires_case_date_validation:
            raise ValueError("Toda referencia C.7 requiere validación temporal por caso.")
        if any(
            (
                self.external_legal_evidence_used,
                self.can_support_current_determination,
                self.can_control_legal_decision,
            )
        ):
            raise ValueError("C.7 no usa evidencia externa ni habilita determinación jurídica.")
        return self


class PrimaryCBRSituationCorpusValidation(BaseModel):
    """Resultado C.7 por cada una de las 37 situaciones primarias."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    situation_id: str = Field(pattern=r"^(P|U)-CBR-SIT-[0-9]{3}$")
    source: PrimaryManual
    source_entry_id: str = Field(pattern=r"^(PRODECON-\d{2}|UNAM-[IVX]+)$")
    historical_regime_context: bool
    article_validations: list[PrimaryCBRArticleCorpusValidation] = Field(
        default_factory=list, max_length=20
    )
    no_explicit_article_reason: str | None = Field(default=None, min_length=10, max_length=500)
    validation_outcome: PrimaryCBRCorpusValidationOutcome
    corpus_validation_completed: bool = True
    corpus_validated: bool
    temporal_validation_pending: bool = True
    current_law_verified: bool = False
    cbr_family_assigned: bool = False
    operational_case_created: bool = False
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def validate_situation_result(self) -> PrimaryCBRSituationCorpusValidation:
        if self.article_validations:
            if self.no_explicit_article_reason is not None:
                raise ValueError("No corresponde razón de ausencia cuando existen citas C.7.")
            outcomes = {item.validation_outcome for item in self.article_validations}
            if PrimaryCBRCorpusValidationOutcome.BLOCKED_CONTENT_MISMATCH in outcomes:
                expected = PrimaryCBRCorpusValidationOutcome.BLOCKED_CONTENT_MISMATCH
            elif PrimaryCBRCorpusValidationOutcome.BLOCKED_DEROGATED in outcomes:
                expected = PrimaryCBRCorpusValidationOutcome.BLOCKED_DEROGATED
            else:
                expected = PrimaryCBRCorpusValidationOutcome.CONSISTENT
            if self.validation_outcome != expected:
                raise ValueError("Resultado de situación C.7 inconsistente con sus artículos.")
            if self.corpus_validated != (expected == PrimaryCBRCorpusValidationOutcome.CONSISTENT):
                raise ValueError("corpus_validated C.7 no coincide con el resultado material.")
        else:
            if not self.no_explicit_article_reason:
                raise ValueError("Situación C.7 sin artículo debe conservar la razón C.6.")
            if self.validation_outcome != PrimaryCBRCorpusValidationOutcome.NO_EXPLICIT_CITATION:
                raise ValueError("Situación sin cita debe quedar como no_explicit_citation.")
            if self.corpus_validated:
                raise ValueError("No puede validarse materialmente una cita que no existe en C.6.")
        if not self.corpus_validation_completed or not self.temporal_validation_pending:
            raise ValueError("C.7 debe completar corpus y dejar pendiente temporalidad por caso.")
        if any(
            (
                self.current_law_verified,
                self.cbr_family_assigned,
                self.operational_case_created,
                self.can_control_legal_decision,
            )
        ):
            raise ValueError("C.7 no adelanta C.8-C.10 ni controla Legal Decision.")
        return self


class PrimaryCBRCorpusValidationReport(BaseModel):
    """Reporte reproducible C.7 de contraste contra el corpus normativo cerrado."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    validation_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    baseline_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    purpose: str = Field(min_length=20, max_length=1200)
    normative_corpus_ids: list[str] = Field(min_length=12, max_length=12)
    temporal_registry_source_sprint: str = Field(min_length=1, max_length=100)
    document_wide_temporal_blocks: list[str] = Field(default_factory=list, max_length=12)
    corpus_snapshots: list[PrimaryCBRNormativeCorpusSnapshot] = Field(min_length=1, max_length=12)
    source_situation_count: int = Field(ge=1)
    explicit_citation_situation_count: int = Field(ge=0)
    no_explicit_citation_situation_count: int = Field(ge=0)
    article_link_count: int = Field(ge=0)
    unique_normative_ref_count: int = Field(ge=0)
    active_consistent_link_count: int = Field(ge=0)
    derogated_link_count: int = Field(ge=0)
    content_mismatch_link_count: int = Field(ge=0)
    corpus_validated_situation_count: int = Field(ge=0)
    blocked_situation_count: int = Field(ge=0)
    situations: list[PrimaryCBRSituationCorpusValidation] = Field(min_length=1)
    verifies_against_closed_internal_corpus: bool = True
    temporal_policy_fail_closed: bool = True
    uses_external_legal_evidence: bool = False
    validates_current_law_for_case: bool = False
    assigns_cbr_families: bool = False
    creates_operational_cases: bool = False
    modifies_existing_cbr_engine: bool = False
    can_control_legal_decision: bool = False

    @field_validator("normative_corpus_ids", "document_wide_temporal_blocks")
    @classmethod
    def unique_ids(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("C.7 no admite identificadores duplicados.")
        return values

    @model_validator(mode="after")
    def validate_report(self) -> PrimaryCBRCorpusValidationReport:
        if len(self.situations) != self.source_situation_count:
            raise ValueError("Conteo de situaciones C.7 inconsistente.")
        situation_ids = [item.situation_id for item in self.situations]
        if len(situation_ids) != len(set(situation_ids)):
            raise ValueError("C.7 contiene situaciones duplicadas.")
        explicit = sum(bool(item.article_validations) for item in self.situations)
        if explicit != self.explicit_citation_situation_count:
            raise ValueError("Conteo de situaciones con cita C.7 inconsistente.")
        if self.source_situation_count - explicit != self.no_explicit_citation_situation_count:
            raise ValueError("Conteo de situaciones sin cita C.7 inconsistente.")
        links = [item for situation in self.situations for item in situation.article_validations]
        if len(links) != self.article_link_count:
            raise ValueError("Conteo de vínculos C.7 inconsistente.")
        if len({item.candidate_normative_ref for item in links}) != self.unique_normative_ref_count:
            raise ValueError("Conteo de referencias únicas C.7 inconsistente.")
        states = [item.article_state for item in links]
        if states.count(PrimaryCBRCorpusArticleState.ACTIVE) != self.active_consistent_link_count:
            raise ValueError("Conteo de vínculos activos C.7 inconsistente.")
        if states.count(PrimaryCBRCorpusArticleState.DEROGATED) != self.derogated_link_count:
            raise ValueError("Conteo de vínculos derogados C.7 inconsistente.")
        if (
            states.count(PrimaryCBRCorpusArticleState.CONTENT_MISMATCH)
            != self.content_mismatch_link_count
        ):
            raise ValueError("Conteo de desajustes materiales C.7 inconsistente.")
        validated = sum(item.corpus_validated for item in self.situations)
        if validated != self.corpus_validated_situation_count:
            raise ValueError("Conteo de situaciones validadas C.7 inconsistente.")
        blocked = sum(
            item.validation_outcome
            in {
                PrimaryCBRCorpusValidationOutcome.BLOCKED_DEROGATED,
                PrimaryCBRCorpusValidationOutcome.BLOCKED_CONTENT_MISMATCH,
            }
            for item in self.situations
        )
        if blocked != self.blocked_situation_count:
            raise ValueError("Conteo de situaciones bloqueadas C.7 inconsistente.")
        if not self.verifies_against_closed_internal_corpus or not self.temporal_policy_fail_closed:
            raise ValueError("C.7 debe validar corpus cerrado con temporalidad fail-closed.")
        if any(
            (
                self.uses_external_legal_evidence,
                self.validates_current_law_for_case,
                self.assigns_cbr_families,
                self.creates_operational_cases,
                self.modifies_existing_cbr_engine,
                self.can_control_legal_decision,
            )
        ):
            raise ValueError("C.7 no adelanta temporalidad, familias u operación CBR.")
        return self
