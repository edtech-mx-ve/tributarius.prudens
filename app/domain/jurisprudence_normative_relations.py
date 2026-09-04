from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.jurisprudence import NormRelationType


class JurisprudenceNormativeUnitType(StrEnum):
    ARTICLE = "article"
    RULE = "rule"


class JurisprudenceNormativeLinkBasis(StrEnum):
    """Base documental admisible para E.3; nunca similitud temática."""

    EXPLICIT_NORMATIVE_MENTION = "explicit_normative_mention"
    EXPLICIT_RELATION_LANGUAGE = "explicit_relation_language"


class JurisprudenceNormativeMention(BaseModel):
    """Mención normativa explícita leída del documento jurisprudencial."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    mention_id: str = Field(pattern=r"^E3-NORM-[0-9]{3}$")
    source_page: int = Field(ge=1)
    source_excerpt: str = Field(min_length=3, max_length=1200)
    legal_unit_type: JurisprudenceNormativeUnitType
    legal_unit: str = Field(min_length=1, max_length=80)
    instrument_match: str | None = Field(default=None, max_length=240)
    candidate_corpus_id: str | None = Field(
        default=None, pattern=r"^[a-z][a-z0-9_]*$"
    )
    candidate_normative_ref: str | None = Field(default=None, max_length=220)
    corpus_in_primary_manifest: bool
    relation_type: NormRelationType
    linkage_basis: JurisprudenceNormativeLinkBasis
    material_relation_explicit: bool
    thematic_similarity_used: Literal[False] = False
    article_or_rule_presence_verified: Literal[False] = False
    temporal_validity_verified: Literal[False] = False
    legal_applicability_evaluated: Literal[False] = False
    binding_effect_evaluated: Literal[False] = False
    can_control_legal_decision: Literal[False] = False

    @model_validator(mode="after")
    def validate_candidate_boundary(self) -> JurisprudenceNormativeMention:
        if self.corpus_in_primary_manifest:
            if self.candidate_corpus_id is None or self.candidate_normative_ref is None:
                raise ValueError(
                    "Una mención vinculada a A.8 requiere corpus y referencia candidata."
                )
        elif self.candidate_normative_ref is not None:
            raise ValueError(
                "Una mención fuera del corpus A.8 no puede recibir referencia normativa interna."
            )
        if self.material_relation_explicit:
            if self.relation_type in {NormRelationType.CITES, NormRelationType.UNKNOWN}:
                raise ValueError(
                    "Una relación material explícita requiere tipo interpretativo concreto."
                )
            if self.linkage_basis is not JurisprudenceNormativeLinkBasis.EXPLICIT_RELATION_LANGUAGE:
                raise ValueError(
                    "La relación material sólo puede derivar de lenguaje explícito de la fuente."
                )
        elif self.relation_type not in {NormRelationType.CITES, NormRelationType.UNKNOWN}:
            raise ValueError(
                "E.3 no puede inferir una relación material sin lenguaje explícito."
            )
        return self


class JurisprudenceNormativeRelationRecord(BaseModel):
    """Contrato E.3: normas relacionadas por evidencia textual, aún no aplicadas al caso."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    document_id: str = Field(min_length=3, max_length=200)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    normative_corpus_ids: list[str] = Field(min_length=1, max_length=12)
    mentions: list[JurisprudenceNormativeMention] = Field(default_factory=list)
    mention_count: int = Field(ge=0)
    linked_to_primary_corpus_count: int = Field(ge=0)
    unresolved_or_external_count: int = Field(ge=0)
    explicit_material_relation_count: int = Field(ge=0)
    source_scope: Literal["session"] = "session"
    user_attached: Literal[True] = True
    relation_extraction_completed: Literal[True] = True
    thematic_similarity_used: Literal[False] = False
    article_or_rule_presence_verified: Literal[False] = False
    temporal_validity_verified: Literal[False] = False
    legal_applicability_evaluated: Literal[False] = False
    binding_effect_evaluated: Literal[False] = False
    can_control_legal_decision: Literal[False] = False

    @field_validator("normative_corpus_ids")
    @classmethod
    def unique_corpus_ids(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("El corpus A.8 no admite identificadores duplicados.")
        return values

    @model_validator(mode="after")
    def validate_counts(self) -> JurisprudenceNormativeRelationRecord:
        if self.mention_count != len(self.mentions):
            raise ValueError("Conteo E.3 de menciones inconsistente.")
        linked = sum(item.corpus_in_primary_manifest for item in self.mentions)
        if linked != self.linked_to_primary_corpus_count:
            raise ValueError("Conteo E.3 de vínculos A.8 inconsistente.")
        if self.mention_count - linked != self.unresolved_or_external_count:
            raise ValueError("Conteo E.3 de menciones no vinculadas inconsistente.")
        material = sum(item.material_relation_explicit for item in self.mentions)
        if material != self.explicit_material_relation_count:
            raise ValueError("Conteo E.3 de relaciones materiales inconsistente.")
        if any(
            item.candidate_corpus_id is not None
            and item.candidate_corpus_id not in self.normative_corpus_ids
            for item in self.mentions
        ):
            raise ValueError("E.3 no puede vincular jurisprudencia fuera del corpus A.8.")
        return self
