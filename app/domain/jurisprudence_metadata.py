from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.jurisprudence_extraction import JurisprudenceExtractedMetadata

_METADATA_FIELDS = {
    "identifier",
    "thesis_number",
    "title",
    "court_or_body",
    "criterion_type",
    "publication_date_text",
    "publication_source",
    "epoch",
    "matter",
    "binding_force_text",
    "binding_effective_date_text",
    "facts_text",
    "legal_criterion_text",
    "justification_text",
    "criterion_text",
    "related_normative_refs",
}


class JurisprudenceMetadataEvidence(BaseModel):
    """Trazabilidad E.2 de un metadato leído expresamente del documento."""

    model_config = ConfigDict(extra="forbid")

    field_name: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=4000)
    source_pages: list[int] = Field(min_length=1, max_length=100)
    extraction_basis: Literal["explicit_label", "explicit_text_pattern"]
    verified: Literal[False] = False

    @field_validator("field_name")
    @classmethod
    def validate_field_name(cls, value: str) -> str:
        if value not in _METADATA_FIELDS:
            raise ValueError("Campo de metadato jurisprudencial no reconocido.")
        return value

    @field_validator("source_pages")
    @classmethod
    def normalize_pages(cls, pages: list[int]) -> list[int]:
        if any(page < 1 for page in pages):
            raise ValueError("Las páginas de procedencia deben ser positivas.")
        unique = sorted(set(pages))
        if len(unique) != len(pages):
            return unique
        return pages


class JurisprudenceMetadataRecord(BaseModel):
    """Contrato E.2: metadatos extraídos y trazables, aún no validados jurídicamente."""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=3, max_length=200)
    original_filename: str = Field(min_length=1, max_length=500)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    extracted: JurisprudenceExtractedMetadata
    evidence: list[JurisprudenceMetadataEvidence] = Field(default_factory=list)
    missing_core_fields: list[str] = Field(default_factory=list, max_length=20)
    source_scope: Literal["session"] = "session"
    user_attached: Literal[True] = True
    metadata_extraction_completed: Literal[True] = True
    metadata_verified: Literal[False] = False
    authenticity_verified: Literal[False] = False
    temporal_validity_verified: Literal[False] = False
    normative_relation_verified: Literal[False] = False
    legal_applicability_evaluated: Literal[False] = False
    binding_force_evaluated: Literal[False] = False
    can_control_legal_decision: Literal[False] = False
