from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class KnowledgeLayer(StrEnum):
    PRODECON = "prodecon"
    UNAM = "unam"
    NORMATIVA = "normativa"
    JURISPRUDENCIA = "jurisprudencia"
    CBR = "cbr"


class LegalUnitType(StrEnum):
    DOCUMENT = "document"
    TITLE = "title"
    CHAPTER = "chapter"
    SECTION = "section"
    ARTICLE = "article"
    FRACTION = "fraction"
    SUBSECTION = "subsection"
    CRITERION = "criterion"
    CASE = "case"


class RelationType(StrEnum):
    SUPPORTS = "supports"
    INTERPRETS = "interprets"
    DERIVES_FROM = "derives_from"
    AMENDS = "amends"
    REPEALS = "repeals"
    RELATES_TO = "relates_to"
    IMPLEMENTS_RULE = "implements_rule"
    FEEDS_CALCULATION = "feeds_calculation"
    SIMILAR_CASE = "similar_case"


class ValidityStatus(StrEnum):
    CURRENT = "current"
    HISTORICAL = "historical"
    FUTURE = "future"
    UNKNOWN = "unknown"


class SourceCreate(BaseModel):
    layer: KnowledgeLayer
    name: str = Field(min_length=2, max_length=250)
    authority: str | None = Field(default=None, max_length=250)
    source_reference: str | None = Field(default=None, max_length=1000)
    verified: bool = False


class LegalUnitCreate(BaseModel):
    source_id: int
    unit_type: LegalUnitType
    identifier: str = Field(min_length=1, max_length=160)
    title: str | None = Field(default=None, max_length=500)
    text: str | None = None
    matter: str | None = Field(default=None, max_length=200)
    jurisdiction: str | None = Field(default="MX", max_length=50)
    parent_unit_id: int | None = None


class NormVersionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    legal_unit_id: int
    version_label: str = Field(min_length=1, max_length=100)
    publication_date: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    fiscal_year: int | None = Field(default=None, ge=1900, le=2200)
    validity_status: ValidityStatus = ValidityStatus.UNKNOWN
    source_reference: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_effective_period(self) -> NormVersionCreate:
        if (
            self.effective_from is not None
            and self.effective_to is not None
            and self.effective_to < self.effective_from
        ):
            raise ValueError("effective_to no puede ser anterior a effective_from")
        return self


class KnowledgeRelationCreate(BaseModel):
    source_unit_id: int
    target_unit_id: int
    relation_type: RelationType
    rationale: str | None = Field(default=None, max_length=1000)


class MasterMatrixEntryCreate(BaseModel):
    module_key: str = Field(pattern=r"^[a-z0-9_]+$", min_length=2, max_length=100)
    module_name: str = Field(min_length=2, max_length=200)
    prodecon_refs: list[str] = Field(default_factory=list)
    unam_refs: list[str] = Field(default_factory=list)
    normative_refs: list[str] = Field(default_factory=list)
    jurisprudential_refs: list[str] = Field(default_factory=list)
    rule_refs: list[str] = Field(default_factory=list)
    calculation_refs: list[str] = Field(default_factory=list)
    cbr_refs: list[str] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=2000)


class MasterMatrixEntryRead(MasterMatrixEntryCreate):
    id: int
