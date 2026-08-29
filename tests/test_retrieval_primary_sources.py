from __future__ import annotations

from app.domain.chunks import (
    ChunkMetadata,
    LegalChunkType,
    LegalHierarchy,
)
from app.domain.documents import SourceType
from rag.evaluation.runtime_retrieval import (
    RetrievalEvalCase,
    evaluate_retrieval_case,
    summarize_evaluation,
)
from rag.retrieval.models import RetrievalHit, RetrievalResult


def _hit(rank: int, document_id: str) -> RetrievalHit:
    return RetrievalHit(
        rank=rank,
        score=1.0 - rank / 10,
        chunk_id=f"chunk-{rank:04d}",
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


def _result(query: str, docs: list[str]) -> RetrievalResult:
    return RetrievalResult(
        query=query,
        requested_top_k=len(docs),
        candidate_count=len(docs),
        returned_count=len(docs),
        hits=[
            _hit(rank, document_id)
            for rank, document_id in enumerate(docs, start=1)
        ],
    )


def test_legacy_expected_documents_remains_compatible() -> None:
    case = RetrievalEvalCase(
        case_id="legacy",
        query="consulta fiscal",
        expected_document_ids={"liva"},
        top_k=5,
    )

    evaluated = evaluate_retrieval_case(
        case,
        _result(case.query, ["cff", "liva", "unam"]),
    )

    assert case.expected_primary_document_ids == {"liva"}
    assert evaluated.primary_first_rank == 2
    assert evaluated.primary_hit_at_3 is True


def test_primary_and_supporting_are_measured_separately() -> None:
    case = RetrievalEvalCase(
        case_id="cpeum",
        query="principios constitucionales tributarios",
        expected_primary_document_ids={"cpeum"},
        expected_supporting_document_ids={"manual_derecho_fiscal_unam"},
        top_k=5,
    )

    evaluated = evaluate_retrieval_case(
        case,
        _result(
            case.query,
            [
                "manual_derecho_fiscal_unam",
                "manual_derecho_fiscal_unam",
                "cff",
                "cpeum",
                "liva",
            ],
        ),
    )

    assert evaluated.first_relevant_rank == 1
    assert evaluated.supporting_first_rank == 1
    assert evaluated.primary_first_rank == 4
    assert evaluated.primary_hit_at_3 is False
    assert evaluated.primary_hit_at_k is True


def test_primary_absence_is_not_hidden_by_supporting_hit() -> None:
    case = RetrievalEvalCase(
        case_id="liva",
        query="tasa general IVA",
        expected_primary_document_ids={"liva"},
        expected_supporting_document_ids={"manual_derecho_fiscal_unam"},
        top_k=5,
    )

    evaluated = evaluate_retrieval_case(
        case,
        _result(
            case.query,
            [
                "manual_derecho_fiscal_unam",
                "rmf_2026",
                "manual_derecho_fiscal_unam",
                "rmf_2026",
                "cff",
            ],
        ),
    )

    assert evaluated.hit_at_1 is True
    assert evaluated.primary_first_rank is None
    assert evaluated.primary_hit_at_k is False


def test_summary_reports_primary_metrics_and_diversity() -> None:
    case_a = RetrievalEvalCase(
        case_id="a",
        query="consulta a",
        expected_primary_document_ids={"liva"},
        top_k=3,
    )
    case_b = RetrievalEvalCase(
        case_id="b",
        query="consulta b",
        expected_primary_document_ids={"cff"},
        top_k=3,
    )
    evaluated = [
        evaluate_retrieval_case(
            case_a,
            _result(case_a.query, ["liva", "liva", "cff"]),
        ),
        evaluate_retrieval_case(
            case_b,
            _result(case_b.query, ["liva", "cff", "unam"]),
        ),
    ]

    summary = summarize_evaluation(evaluated)

    assert summary.primary_hit_at_1 == 0.5
    assert summary.primary_hit_at_3 == 1.0
    assert summary.primary_hit_at_k == 1.0
    assert summary.primary_mrr == 0.75
    assert summary.mean_unique_documents_top_k == 2.5
