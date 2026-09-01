from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.documents import SourceType


class EvidenceItem(BaseModel):
    chunk_id: str = Field(min_length=8, max_length=300)
    score: float
    source_type: SourceType
    source_filename: str = Field(min_length=1, max_length=300)
    legal_identifier: str | None = Field(default=None, max_length=300)
    page_start: int | None = Field(default=None, ge=1)
    fiscal_year: int | None = Field(default=None, ge=1900, le=2200)
    version_label: str | None = Field(default=None, max_length=100)
    text: str = Field(min_length=1)


class DeterministicEvidence(BaseModel):
    prodecon_orientation_refs: list[str] = Field(default_factory=list, max_length=100)
    unam_foundation_refs: list[str] = Field(default_factory=list, max_length=100)
    normative_evidence_refs: list[str] = Field(default_factory=list, max_length=100)
    applicable_normative_refs: list[str] = Field(default_factory=list, max_length=100)
    rule_conclusions: list[str] = Field(default_factory=list, max_length=100)
    calculations: list[str] = Field(default_factory=list, max_length=50)
    similar_cases: list[str] = Field(default_factory=list, max_length=20)
    jurisprudential_criteria: list[str] = Field(default_factory=list, max_length=20)
    requires_human_review: bool = False


class LLMGenerationContext(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    evidence: list[EvidenceItem] = Field(min_length=1, max_length=20)
    deterministic_evidence: DeterministicEvidence | None = None


class LlamaStructuredAnswer(BaseModel):
    summary: str = Field(min_length=1, max_length=4000)
    analysis: str = Field(min_length=1, max_length=12000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    uncertainties: list[str] = Field(default_factory=list, max_length=20)
    requires_human_review: bool = False


class RAGExplanation(BaseModel):
    question: str = Field(min_length=1)
    provider_name: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    generation_performed: bool
    retrieved_count: int = Field(ge=0)
    answer: LlamaStructuredAnswer
