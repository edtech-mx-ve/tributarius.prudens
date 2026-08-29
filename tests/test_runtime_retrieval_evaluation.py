from __future__ import annotations

from app.domain.chunks import ChunkMetadata, LegalChunk, LegalChunkType, LegalHierarchy
from app.domain.documents import SourceType
from rag.evaluation.runtime_retrieval import (
    RetrievalEvalCase,
    diagnose_chunk_lengths,
    evaluate_retrieval_case,
    summarize_evaluation,
)
from rag.retrieval.models import RetrievalHit, RetrievalResult


def _hit(rank: int, document_id: str) -> RetrievalHit:
    return RetrievalHit(
        rank=rank,
        score=1.0 - rank / 10,
        chunk_id=f"chunk-{rank}",
        text="Texto fiscal",
        metadata=ChunkMetadata(
            document_id=document_id,
            source_type=SourceType.NORMATIVA,
            source_filename=f"{document_id}.md",
            chunk_index=rank - 1,
            chunk_type=LegalChunkType.ARTICLE,
            hierarchy=LegalHierarchy(),
            source_sha256="a" * 64,
        ),
    )


def test_evaluate_case_finds_first_relevant_rank() -> None:
    case = RetrievalEvalCase(
        case_id="lisr",
        query="deducciones personales",
        expected_document_ids={"lisr"},
        top_k=5,
    )
    result = RetrievalResult(
        query=case.query,
        requested_top_k=5,
        candidate_count=10,
        returned_count=3,
        hits=[_hit(1, "cff"), _hit(2, "lisr"), _hit(3, "liva")],
    )

    evaluated = evaluate_retrieval_case(case, result)

    assert evaluated.first_relevant_rank == 2
    assert evaluated.hit_at_1 is False
    assert evaluated.hit_at_3 is True
    assert evaluated.hit_at_k is True
    assert evaluated.reciprocal_rank == 0.5


def test_summary_computes_hit_rates_and_mrr() -> None:
    cases = []
    for case_id, rank in (("a", 1), ("b", 3), ("c", None)):
        case = RetrievalEvalCase(
            case_id=case_id,
            query=f"consulta {case_id}",
            expected_document_ids={"target"},
            top_k=5,
        )
        docs = ["target" if position == rank else f"doc{position}" for position in range(1, 6)]
        result = RetrievalResult(
            query=case.query,
            requested_top_k=5,
            candidate_count=5,
            returned_count=5,
            hits=[_hit(position, doc) for position, doc in enumerate(docs, start=1)],
        )
        cases.append(evaluate_retrieval_case(case, result))

    summary = summarize_evaluation(cases)

    assert summary.hit_at_1 == 1 / 3
    assert summary.hit_at_3 == 2 / 3
    assert summary.hit_at_k == 2 / 3
    assert summary.mrr == (1.0 + 1 / 3) / 3


class FakeTokenCounter:
    max_seq_length = 10

    def count_tokens(self, text: str) -> int:
        return len(text.split())


def test_length_diagnostic_flags_chunk_over_model_limit() -> None:
    chunk = LegalChunk(
        chunk_id="long-chunk",
        text=" ".join(["tributario"] * 20),
        metadata=ChunkMetadata(
            document_id="cff",
            source_type=SourceType.NORMATIVA,
            source_filename="cff.md",
            chunk_index=0,
            chunk_type=LegalChunkType.ARTICLE,
            hierarchy=LegalHierarchy(),
            source_sha256="b" * 64,
        ),
    )

    diagnostics = diagnose_chunk_lengths([chunk], FakeTokenCounter())

    assert len(diagnostics) == 1
    assert diagnostics[0].truncation_risk is True
    assert diagnostics[0].token_ratio > 1.0
