from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PrimaryManual(StrEnum):
    PRODECON = "prodecon"
    UNAM = "unam"


class PrimaryKnowledgeEntry(BaseModel):
    """Entrada primaria de navegación derivada de PRODECON o UNAM.

    No constituye fundamento normativo ni puede controlar una determinación.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    entry_id: str = Field(pattern=r"^(PRODECON-\d{2}|UNAM-[IVX]+)$")
    manual: PrimaryManual
    order: int = Field(ge=1, le=12)
    title: str = Field(min_length=3, max_length=200)
    functional_module: str = Field(min_length=3, max_length=200)
    related_entries: list[str] = Field(default_factory=list, max_length=19)
    legal_dimensions: list[str] = Field(min_length=1, max_length=20)
    rbs_families: list[str] = Field(min_length=1, max_length=20)
    cbr_families: list[str] = Field(min_length=1, max_length=20)
    candidate_normative_sources: list[str] = Field(default_factory=list, max_length=20)
    historical_content: bool = False
    requires_temporal_validation: bool = True
    requires_normative_validation: bool = True
    can_control_legal_decision: bool = False

    @field_validator(
        "related_entries",
        "legal_dimensions",
        "rbs_families",
        "cbr_families",
        "candidate_normative_sources",
    )
    @classmethod
    def unique_values(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("Las listas de conocimiento primario no admiten duplicados.")
        return values

    @model_validator(mode="after")
    def enforce_closed_evidence_boundary(self) -> PrimaryKnowledgeEntry:
        if not self.requires_normative_validation:
            raise ValueError("PRODECON/UNAM siempre requieren validación normativa.")
        if self.can_control_legal_decision:
            raise ValueError("PRODECON/UNAM no pueden controlar Legal Decision.")
        if self.manual is PrimaryManual.PRODECON and not self.entry_id.startswith("PRODECON-"):
            raise ValueError("entry_id incompatible con manual=prodecon.")
        if self.manual is PrimaryManual.UNAM and not self.entry_id.startswith("UNAM-"):
            raise ValueError("entry_id incompatible con manual=unam.")
        return self


class PrimaryKnowledgeMap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    purpose: str = Field(min_length=20, max_length=1000)
    entries: list[PrimaryKnowledgeEntry] = Field(min_length=19, max_length=19)

    @model_validator(mode="after")
    def validate_primary_map(self) -> PrimaryKnowledgeMap:
        prodecon = [item for item in self.entries if item.manual is PrimaryManual.PRODECON]
        unam = [item for item in self.entries if item.manual is PrimaryManual.UNAM]
        if len(prodecon) != 12:
            raise ValueError("La guía primaria debe contener 12 apartados PRODECON.")
        if len(unam) != 7:
            raise ValueError("La guía primaria debe contener 7 capítulos UNAM.")
        if [item.order for item in prodecon] != list(range(1, 13)):
            raise ValueError("PRODECON debe conservar el orden 1..12.")
        if [item.order for item in unam] != list(range(1, 8)):
            raise ValueError("UNAM debe conservar el orden I..VII mediante order=1..7.")
        ids = [item.entry_id for item in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("entry_id duplicado en la guía primaria.")
        known = set(ids)
        unknown = {
            ref
            for item in self.entries
            for ref in item.related_entries
            if ref not in known
        }
        if unknown:
            raise ValueError(f"Referencias cruzadas desconocidas: {sorted(unknown)}")
        return self


class PrimaryTaxonomyKind(StrEnum):
    PROBLEM = "problem"
    INSTITUTION = "institution"
    RELATION = "relation"


class PrimaryTaxonomyConcept(BaseModel):
    """Concepto jurídico-fiscal computable usado para activar navegación primaria."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    concept_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    kind: PrimaryTaxonomyKind
    label: str = Field(min_length=3, max_length=160)
    aliases: list[str] = Field(default_factory=list, max_length=20)
    primary_entries: list[str] = Field(min_length=1, max_length=19)
    rbs_families: list[str] = Field(min_length=1, max_length=20)
    cbr_families: list[str] = Field(min_length=1, max_length=20)
    candidate_normative_sources: list[str] = Field(default_factory=list, max_length=20)
    requires_normative_validation: bool = True
    can_control_legal_decision: bool = False

    @field_validator(
        "aliases",
        "primary_entries",
        "rbs_families",
        "cbr_families",
        "candidate_normative_sources",
    )
    @classmethod
    def unique_taxonomy_values(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("La taxonomía primaria no admite valores duplicados.")
        return values

    @model_validator(mode="after")
    def enforce_navigation_only(self) -> PrimaryTaxonomyConcept:
        if not self.requires_normative_validation:
            raise ValueError("La taxonomía primaria siempre exige validación normativa.")
        if self.can_control_legal_decision:
            raise ValueError("La taxonomía primaria no puede controlar Legal Decision.")
        return self


class PrimaryLegalTaxonomy(BaseModel):
    """Taxonomía común para problemas, instituciones y relaciones jurídico-fiscales."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    purpose: str = Field(min_length=20, max_length=1000)
    concepts: list[PrimaryTaxonomyConcept] = Field(min_length=10, max_length=200)

    @model_validator(mode="after")
    def validate_taxonomy(self) -> PrimaryLegalTaxonomy:
        ids = [concept.concept_id for concept in self.concepts]
        if len(ids) != len(set(ids)):
            raise ValueError("concept_id duplicado en la taxonomía primaria.")
        kinds = {concept.kind for concept in self.concepts}
        if kinds != set(PrimaryTaxonomyKind):
            raise ValueError("La taxonomía debe cubrir problema, institución y relación.")
        return self

class FiscalProblemInstitutionKind(StrEnum):
    PROBLEM = "problem"
    INSTITUTION = "institution"


class FiscalProblemInstitution(BaseModel):
    """Problema o institución fiscal de A.6, enlazado a la guía primaria."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    concept_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    kind: FiscalProblemInstitutionKind
    label: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=20, max_length=1000)
    aliases: list[str] = Field(default_factory=list, max_length=20)
    primary_entries: list[str] = Field(min_length=1, max_length=19)
    related_concepts: list[str] = Field(default_factory=list, max_length=30)
    relation_ids: list[str] = Field(min_length=1, max_length=30)
    rbs_families: list[str] = Field(min_length=1, max_length=20)
    cbr_families: list[str] = Field(min_length=1, max_length=20)
    candidate_normative_sources: list[str] = Field(default_factory=list, max_length=20)
    requires_normative_validation: bool = True
    can_control_legal_decision: bool = False

    @field_validator(
        "aliases",
        "primary_entries",
        "related_concepts",
        "relation_ids",
        "rbs_families",
        "cbr_families",
        "candidate_normative_sources",
    )
    @classmethod
    def unique_problem_values(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("A.6 no admite valores duplicados.")
        return values

    @model_validator(mode="after")
    def enforce_problem_boundary(self) -> FiscalProblemInstitution:
        if not self.requires_normative_validation or self.can_control_legal_decision:
            raise ValueError("A.6 solo orienta y siempre exige validación normativa.")
        return self


class FiscalProblemInstitutionTaxonomy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    purpose: str = Field(min_length=20, max_length=1000)
    concepts: list[FiscalProblemInstitution] = Field(min_length=2, max_length=200)

    @model_validator(mode="after")
    def validate_problem_taxonomy(self) -> FiscalProblemInstitutionTaxonomy:
        ids = [concept.concept_id for concept in self.concepts]
        if len(ids) != len(set(ids)):
            raise ValueError("concept_id duplicado en A.6.")
        if {concept.kind for concept in self.concepts} != set(FiscalProblemInstitutionKind):
            raise ValueError("A.6 debe contener problemas e instituciones.")
        known = set(ids)
        unknown = {
            ref
            for concept in self.concepts
            for ref in concept.related_concepts
            if ref not in known
        }
        if unknown:
            raise ValueError(f"A.6 contiene conceptos relacionados desconocidos: {sorted(unknown)}")
        return self


class LegalRelationTaxonomyEntry(BaseModel):
    """Relación jurídica A.7 que expresa qué vínculo debe investigarse."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    relation_id: str = Field(pattern=r"^REL-[A-Z0-9-]+$")
    label: str = Field(min_length=3, max_length=180)
    description: str = Field(min_length=20, max_length=1000)
    subject_role: str = Field(min_length=2, max_length=120)
    object_role: str = Field(min_length=2, max_length=160)
    relation_type: str = Field(min_length=2, max_length=100)
    problem_concepts: list[str] = Field(default_factory=list, max_length=30)
    institution_concepts: list[str] = Field(min_length=1, max_length=30)
    primary_entries: list[str] = Field(min_length=1, max_length=19)
    rbs_families: list[str] = Field(min_length=1, max_length=20)
    cbr_families: list[str] = Field(min_length=1, max_length=20)
    candidate_normative_sources: list[str] = Field(default_factory=list, max_length=20)
    temporal_sensitive: bool = True
    requires_normative_validation: bool = True
    can_control_legal_decision: bool = False

    @field_validator(
        "problem_concepts",
        "institution_concepts",
        "primary_entries",
        "rbs_families",
        "cbr_families",
        "candidate_normative_sources",
    )
    @classmethod
    def unique_relation_values(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("A.7 no admite valores duplicados.")
        return values

    @model_validator(mode="after")
    def enforce_relation_boundary(self) -> LegalRelationTaxonomyEntry:
        if not self.requires_normative_validation or self.can_control_legal_decision:
            raise ValueError("A.7 solo orienta y siempre exige validación normativa.")
        return self


class LegalRelationTaxonomy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    purpose: str = Field(min_length=20, max_length=1000)
    relations: list[LegalRelationTaxonomyEntry] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_relation_taxonomy(self) -> LegalRelationTaxonomy:
        ids = [relation.relation_id for relation in self.relations]
        if len(ids) != len(set(ids)):
            raise ValueError("relation_id duplicado en A.7.")
        return self


class PrimaryKnowledgeComponent(StrEnum):
    KNOWLEDGE_MAP = "knowledge_map"
    LEGAL_TAXONOMY = "legal_taxonomy"
    PROBLEM_INSTITUTION_TAXONOMY = "problem_institution_taxonomy"
    RELATION_TAXONOMY = "relation_taxonomy"


class PrimaryKnowledgeManifest(BaseModel):
    """Contrato versionado que fija los componentes de conocimiento A.1-A.7."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    knowledge_version: str = Field(pattern=r"^1\.\d+\.\d+$")
    effective_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    purpose: str = Field(min_length=20, max_length=1000)
    components: dict[PrimaryKnowledgeComponent, str]
    normative_corpus_ids: list[str] = Field(min_length=12, max_length=12)
    permanent_source_count: int = Field(default=14, ge=14, le=14)
    primary_manual_count: int = Field(default=2, ge=2, le=2)
    normative_corpus_count: int = Field(default=12, ge=12, le=12)
    requires_normative_validation: bool = True
    can_control_legal_decision: bool = False

    @field_validator("normative_corpus_ids")
    @classmethod
    def unique_normative_corpus_ids(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("A.8 exige doce corpus normativos únicos.")
        return values

    @model_validator(mode="after")
    def validate_manifest_contract(self) -> PrimaryKnowledgeManifest:
        if set(self.components) != set(PrimaryKnowledgeComponent):
            raise ValueError("A.8 debe registrar exactamente los cuatro componentes A.1-A.7.")
        if not self.requires_normative_validation or self.can_control_legal_decision:
            raise ValueError("A.8 es conocimiento orientador y no controla Legal Decision.")
        return self


class PrimaryLegalKnowledgeResource(BaseModel):
    """Snapshot computable, versionado y trazable de la base primaria A.1-A.8."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str
    knowledge_version: str
    effective_date: str
    knowledge_map: PrimaryKnowledgeMap
    legal_taxonomy: PrimaryLegalTaxonomy
    problem_institution_taxonomy: FiscalProblemInstitutionTaxonomy
    relation_taxonomy: LegalRelationTaxonomy
    normative_corpus_ids: tuple[str, ...]
    rbs_families: tuple[str, ...]
    cbr_families: tuple[str, ...]
    canonical_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    requires_normative_validation: bool = True
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def enforce_resource_boundary(self) -> PrimaryLegalKnowledgeResource:
        if not self.requires_normative_validation or self.can_control_legal_decision:
            raise ValueError("El recurso A.8 no puede controlar Legal Decision.")
        return self
