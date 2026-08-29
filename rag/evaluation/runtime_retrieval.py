from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import mean
from typing import Protocol

from pydantic import BaseModel, Field, model_validator

from rag.indexing.builder import render_embedding_text
from rag.retrieval.models import RetrievalResult


class RetrievalEvalCase(BaseModel):
    case_id: str = Field(min_length=1, max_length=80)
    query: str = Field(min_length=3, max_length=1000)

    # Compatibilidad con Sprint 19E.
    expected_document_ids: set[str] = Field(default_factory=set)

    # Sprint 19F.1: distingue objetivo principal de fuentes complementarias.
    expected_primary_document_ids: set[str] = Field(default_factory=set)
    expected_supporting_document_ids: set[str] = Field(default_factory=set)
    top_k: int = Field(default=5, ge=1, le=20)

    @model_validator(mode="after")
    def normalize_expected_documents(self) -> RetrievalEvalCase:
        if not self.expected_primary_document_ids:
            if not self.expected_document_ids:
                raise ValueError(
                    "Se requiere expected_primary_document_ids o "
                    "expected_document_ids."
                )
            self.expected_primary_document_ids = set(self.expected_document_ids)

        union = (
            set(self.expected_primary_document_ids)
            | set(self.expected_supporting_document_ids)
        )
        if not self.expected_document_ids:
            self.expected_document_ids = union
        else:
            self.expected_document_ids |= union
        return self


class RetrievalCaseResult(BaseModel):
    case_id: str
    query: str
    expected_document_ids: set[str]
    expected_primary_document_ids: set[str]
    expected_supporting_document_ids: set[str]
    returned_document_ids: list[str]

    first_relevant_rank: int | None = Field(default=None, ge=1)
    primary_first_rank: int | None = Field(default=None, ge=1)
    supporting_first_rank: int | None = Field(default=None, ge=1)

    reciprocal_rank: float = Field(ge=0.0, le=1.0)
    primary_reciprocal_rank: float = Field(ge=0.0, le=1.0)

    hit_at_1: bool
    hit_at_3: bool
    hit_at_k: bool
    primary_hit_at_1: bool
    primary_hit_at_3: bool
    primary_hit_at_k: bool

    unique_document_count: int = Field(ge=0)
    duplicate_document_count: int = Field(ge=0)


class RetrievalEvaluationSummary(BaseModel):
    case_count: int = Field(ge=1)
    hit_at_1: float = Field(ge=0.0, le=1.0)
    hit_at_3: float = Field(ge=0.0, le=1.0)
    hit_at_k: float = Field(ge=0.0, le=1.0)
    mrr: float = Field(ge=0.0, le=1.0)

    primary_hit_at_1: float = Field(ge=0.0, le=1.0)
    primary_hit_at_3: float = Field(ge=0.0, le=1.0)
    primary_hit_at_k: float = Field(ge=0.0, le=1.0)
    primary_mrr: float = Field(ge=0.0, le=1.0)

    mean_unique_documents_top_k: float = Field(ge=0.0)
    results: list[RetrievalCaseResult]


@dataclass(frozen=True)
class ChunkLengthDiagnostic:
    chunk_id: str
    document_id: str
    chars: int
    tokens: int
    max_seq_length: int

    @property
    def truncation_risk(self) -> bool:
        return self.tokens > self.max_seq_length

    @property
    def token_ratio(self) -> float:
        return self.tokens / self.max_seq_length


class TokenCounterLike(Protocol):
    @property
    def max_seq_length(self) -> int: ...

    def count_tokens(self, text: str) -> int: ...


def _first_rank(returned: Sequence[str], expected: set[str]) -> int | None:
    if not expected:
        return None
    return next(
        (
            rank
            for rank, document_id in enumerate(returned, start=1)
            if document_id in expected
        ),
        None,
    )


def evaluate_retrieval_case(
    case: RetrievalEvalCase,
    result: RetrievalResult,
) -> RetrievalCaseResult:
    returned = [hit.metadata.document_id for hit in result.hits]
    first_rank = _first_rank(returned, case.expected_document_ids)
    primary_rank = _first_rank(returned, case.expected_primary_document_ids)
    supporting_rank = _first_rank(
        returned,
        case.expected_supporting_document_ids,
    )

    reciprocal_rank = 0.0 if first_rank is None else 1.0 / first_rank
    primary_rr = 0.0 if primary_rank is None else 1.0 / primary_rank
    unique_count = len(set(returned))

    return RetrievalCaseResult(
        case_id=case.case_id,
        query=case.query,
        expected_document_ids=case.expected_document_ids,
        expected_primary_document_ids=case.expected_primary_document_ids,
        expected_supporting_document_ids=case.expected_supporting_document_ids,
        returned_document_ids=returned,
        first_relevant_rank=first_rank,
        primary_first_rank=primary_rank,
        supporting_first_rank=supporting_rank,
        reciprocal_rank=reciprocal_rank,
        primary_reciprocal_rank=primary_rr,
        hit_at_1=first_rank == 1,
        hit_at_3=first_rank is not None and first_rank <= 3,
        hit_at_k=first_rank is not None and first_rank <= case.top_k,
        primary_hit_at_1=primary_rank == 1,
        primary_hit_at_3=primary_rank is not None and primary_rank <= 3,
        primary_hit_at_k=primary_rank is not None and primary_rank <= case.top_k,
        unique_document_count=unique_count,
        duplicate_document_count=max(0, len(returned) - unique_count),
    )


def summarize_evaluation(
    results: Sequence[RetrievalCaseResult],
) -> RetrievalEvaluationSummary:
    if not results:
        raise ValueError("La evaluación requiere al menos un caso.")
    return RetrievalEvaluationSummary(
        case_count=len(results),
        hit_at_1=mean(float(item.hit_at_1) for item in results),
        hit_at_3=mean(float(item.hit_at_3) for item in results),
        hit_at_k=mean(float(item.hit_at_k) for item in results),
        mrr=mean(item.reciprocal_rank for item in results),
        primary_hit_at_1=mean(
            float(item.primary_hit_at_1) for item in results
        ),
        primary_hit_at_3=mean(
            float(item.primary_hit_at_3) for item in results
        ),
        primary_hit_at_k=mean(
            float(item.primary_hit_at_k) for item in results
        ),
        primary_mrr=mean(item.primary_reciprocal_rank for item in results),
        mean_unique_documents_top_k=mean(
            item.unique_document_count for item in results
        ),
        results=list(results),
    )


def diagnose_chunk_lengths(
    chunks: Sequence[object],
    token_counter: TokenCounterLike,
) -> list[ChunkLengthDiagnostic]:
    diagnostics: list[ChunkLengthDiagnostic] = []
    max_seq_length = token_counter.max_seq_length
    for raw_chunk in chunks:
        chunk = raw_chunk
        text = render_embedding_text(chunk)  # type: ignore[arg-type]
        diagnostics.append(
            ChunkLengthDiagnostic(
                chunk_id=chunk.chunk_id,  # type: ignore[attr-defined]
                document_id=chunk.metadata.document_id,  # type: ignore[attr-defined]
                chars=len(text),
                tokens=token_counter.count_tokens(text),
                max_seq_length=max_seq_length,
            )
        )
    return diagnostics
