from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.primary_cbr_problem_institution import PrimaryCBRClassifiedSimilaritySeed
from app.domain.primary_legal_knowledge import PrimaryManual


class PrimaryCBRCitationLinkageBasis(StrEnum):
    """Base permitida para C.6: cita normativa explícita en la fuente primaria."""

    EXPLICIT_SOURCE_CITATION = "explicit_source_citation"


class PrimaryCBRCitedArticleLink(BaseModel):
    """Artículo citado por PRODECON/UNAM, normalizado sólo como candidato de corpus."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    link_id: str = Field(pattern=r"^C6-(P|U)-LNK-[0-9]{3}-[0-9]{2}$")
    source_page: int = Field(ge=1, le=10000)
    source_citation_text: str = Field(min_length=3, max_length=700)
    source_instrument_as_printed: str = Field(min_length=2, max_length=200)
    candidate_corpus_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    article: str = Field(pattern=r"^[0-9]+(?:-[A-Za-z])?$")
    qualifier: str | None = Field(default=None, min_length=2, max_length=200)
    candidate_normative_ref: str = Field(
        pattern=r"^[a-z][a-z0-9_]*:articulo_[0-9]+(?:_[a-z])?$"
    )
    linkage_basis: PrimaryCBRCitationLinkageBasis = (
        PrimaryCBRCitationLinkageBasis.EXPLICIT_SOURCE_CITATION
    )
    source_citation_only: bool = True
    requires_corpus_validation: bool = True
    requires_temporal_validation: bool = True
    article_presence_verified: bool = False
    article_content_verified: bool = False
    current_law_verified: bool = False
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def validate_boundary(self) -> PrimaryCBRCitedArticleLink:
        expected_article = self.article.lower().replace("-", "_")
        expected_ref = f"{self.candidate_corpus_id}:articulo_{expected_article}"
        if self.candidate_normative_ref != expected_ref:
            raise ValueError("La referencia candidata C.6 no coincide con corpus/artículo.")
        if not self.source_citation_only:
            raise ValueError("C.6 sólo registra citas explícitas de la fuente.")
        if not self.requires_corpus_validation or not self.requires_temporal_validation:
            raise ValueError("Toda cita C.6 debe esperar C.7 y validación temporal.")
        if any(
            (
                self.article_presence_verified,
                self.article_content_verified,
                self.current_law_verified,
                self.can_control_legal_decision,
            )
        ):
            raise ValueError("C.6 no verifica contenido/vigencia ni controla Legal Decision.")
        return self


class PrimaryCBRArticleLinkedSituation(BaseModel):
    """Situación C.5 enriquecida únicamente con artículos citados en C.2/C.3."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    situation_id: str = Field(pattern=r"^(P|U)-CBR-SIT-[0-9]{3}$")
    source: PrimaryManual
    source_entry_id: str = Field(pattern=r"^(PRODECON-\d{2}|UNAM-[IVX]+)$")
    historical_regime_context: bool
    primary_problem_id: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]*$")
    primary_institution_id: str | None = Field(
        default=None, pattern=r"^[a-z][a-z0-9_]*$"
    )
    similarity_seed: PrimaryCBRClassifiedSimilaritySeed
    unresolved_required_case_fields: list[str] = Field(default_factory=list, max_length=5)
    article_links: list[PrimaryCBRCitedArticleLink] = Field(default_factory=list, max_length=20)
    no_explicit_article_reason: str | None = Field(default=None, min_length=10, max_length=500)
    facts_normalized: bool = True
    problem_institution_classified: bool = True
    normative_articles_linked: bool = True
    corpus_validated: bool = False
    cbr_family_assigned: bool = False
    operational_case_created: bool = False
    can_control_legal_decision: bool = False

    @field_validator("unresolved_required_case_fields")
    @classmethod
    def unique_unresolved(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("C.6 no admite campos CBR pendientes duplicados.")
        return values

    @model_validator(mode="after")
    def validate_linkage(self) -> PrimaryCBRArticleLinkedSituation:
        link_ids = [link.link_id for link in self.article_links]
        if len(link_ids) != len(set(link_ids)):
            raise ValueError("C.6 no admite vínculos de artículo duplicados.")
        expected_prefix = f"C6-{self.situation_id[0]}-LNK-{self.situation_id[-3:]}-"
        if any(not link_id.startswith(expected_prefix) for link_id in link_ids):
            raise ValueError("Los link_id C.6 deben corresponder a su situation_id.")
        if self.article_links:
            if self.no_explicit_article_reason is not None:
                raise ValueError("No corresponde razón de ausencia cuando existen citas C.6.")
        elif not self.no_explicit_article_reason:
            raise ValueError("Una situación sin cita expresa debe registrar la razón C.6.")
        if not (
            self.facts_normalized
            and self.problem_institution_classified
            and self.normative_articles_linked
        ):
            raise ValueError("C.6 requiere C.4, C.5 y enlace de citas completados.")
        if any(
            (
                self.corpus_validated,
                self.cbr_family_assigned,
                self.operational_case_created,
                self.can_control_legal_decision,
            )
        ):
            raise ValueError("C.6 no puede adelantar C.7-C.10 ni controlar Legal Decision.")
        return self


class PrimaryCBRNormativeCitationLinkage(BaseModel):
    """Recurso C.6 de artículos citados por las 37 situaciones CBR primarias."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    baseline_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    purpose: str = Field(min_length=20, max_length=1200)
    linkage_scope: str = Field(min_length=20, max_length=500)
    primary_manifest_resource: str = Field(min_length=5, max_length=200)
    source_situation_count: int = Field(ge=1)
    linked_situation_count: int = Field(ge=0)
    unlinked_situation_count: int = Field(ge=0)
    article_link_count: int = Field(ge=0)
    unique_candidate_normative_ref_count: int = Field(ge=0)
    candidate_corpus_ids: list[str] = Field(min_length=1, max_length=12)
    situations: list[PrimaryCBRArticleLinkedSituation] = Field(min_length=1)
    links_normative_articles: bool = True
    verifies_article_presence: bool = False
    validates_current_law: bool = False
    assigns_cbr_families: bool = False
    creates_operational_cases: bool = False
    modifies_existing_cbr_engine: bool = False
    source_is_normative_authority: bool = False
    can_control_legal_decision: bool = False

    @field_validator("candidate_corpus_ids")
    @classmethod
    def unique_corpus_ids(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("C.6 no admite corpus candidatos duplicados.")
        return values

    @model_validator(mode="after")
    def validate_counts_and_boundary(self) -> PrimaryCBRNormativeCitationLinkage:
        if len(self.situations) != self.source_situation_count:
            raise ValueError("Conteo de situaciones C.6 inconsistente.")
        linked = sum(bool(item.article_links) for item in self.situations)
        if linked != self.linked_situation_count:
            raise ValueError("Conteo de situaciones con cita C.6 inconsistente.")
        if self.source_situation_count - linked != self.unlinked_situation_count:
            raise ValueError("Conteo de situaciones sin cita C.6 inconsistente.")
        links = [link for item in self.situations for link in item.article_links]
        if len(links) != self.article_link_count:
            raise ValueError("Conteo de vínculos de artículo C.6 inconsistente.")
        if len({link.candidate_normative_ref for link in links}) != (
            self.unique_candidate_normative_ref_count
        ):
            raise ValueError("Conteo de referencias candidatas únicas C.6 inconsistente.")
        if {link.candidate_corpus_id for link in links} != set(self.candidate_corpus_ids):
            raise ValueError("Corpus candidatos C.6 inconsistentes con los vínculos.")
        if not self.links_normative_articles:
            raise ValueError("C.6 debe marcar como completado el enlace de artículos citados.")
        if any(
            (
                self.verifies_article_presence,
                self.validates_current_law,
                self.assigns_cbr_families,
                self.creates_operational_cases,
                self.modifies_existing_cbr_engine,
                self.source_is_normative_authority,
                self.can_control_legal_decision,
            )
        ):
            raise ValueError("C.6 no debe adelantar validación, familias u operación CBR.")
        return self
