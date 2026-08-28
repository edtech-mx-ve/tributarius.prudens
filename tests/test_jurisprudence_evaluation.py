from datetime import date
from pathlib import Path

from app.domain.chunks import ChunkMetadata, LegalChunkType, LegalHierarchy
from app.domain.documents import SourceType
from app.domain.jurisprudence import JurisprudenceActivationDecision
from jurisprudence.evaluation import evaluate_jurisprudence_retrieval
from jurisprudence.loader import load_jurisprudence_metadata
from jurisprudence.retrieval import JurisprudenceRetriever
from rag.retrieval.models import RetrievalHit, RetrievalResult


def chunk_metadata(document_id: str) -> ChunkMetadata:
    return ChunkMetadata(
        document_id=document_id,
        source_type=SourceType.JURISPRUDENCIA,
        source_filename=f"{document_id}.md",
        chunk_index=0,
        chunk_type=LegalChunkType.PARAGRAPH,
        legal_identifier="Criterio sintético",
        page_start=1,
        page_end=1,
        hierarchy=LegalHierarchy(),
        source_sha256="a" * 64,
    )


class FakeRetriever:
    def __init__(self, ids: list[str]) -> None:
        self.ids = ids

    def search(self, query: str, *, top_k: int = 5, filters=None) -> RetrievalResult:
        del query, top_k, filters
        hits = [
            RetrievalHit(
                rank=index,
                score=0.9,
                chunk_id=f"{document_id}-chunk-0001",
                text="Fixture sintética.",
                metadata=chunk_metadata(document_id),
            )
            for index, document_id in enumerate(self.ids, start=1)
        ]
        return RetrievalResult(
            query="q",
            requested_top_k=5,
            candidate_count=len(hits),
            returned_count=len(hits),
            hits=hits,
        )


def decision() -> JurisprudenceActivationDecision:
    return JurisprudenceActivationDecision(
        activated=True,
        reason="explicit_request",
        detail="Solicitud explícita.",
    )


def test_jurisprudence_evaluation_passes_relevant_fixture() -> None:
    registry = load_jurisprudence_metadata(
        Path("jurisprudence/fixtures/metadata_synthetic.jsonl")
    )
    result = JurisprudenceRetriever(
        FakeRetriever(["jur-test-current"]),
        registry,
    ).search(
        "q",
        activation=decision(),
        query_date=date(2026, 8, 28),
        applicable_normative_refs={"NORM_TEST_ISR_2026"},
        matter="fiscal",
    )
    evaluation = evaluate_jurisprudence_retrieval(
        result,
        expected_activated=True,
        expected_document_ids={"jur-test-current"},
        expected_norm_related_document_ids={"jur-test-current"},
    )
    assert evaluation.passed is True
    assert evaluation.spurious_retrieval_rate == 0.0


def test_jurisprudence_evaluation_detects_spurious_retrieval() -> None:
    registry = load_jurisprudence_metadata(
        Path("jurisprudence/fixtures/metadata_synthetic.jsonl")
    )
    result = JurisprudenceRetriever(
        FakeRetriever(["jur-test-current", "jur-test-historical"]),
        registry,
    ).search(
        "q",
        activation=decision(),
        query_date=date(2026, 8, 28),
        applicable_normative_refs={"NORM_TEST_ISR_2026"},
    )
    evaluation = evaluate_jurisprudence_retrieval(
        result,
        expected_activated=True,
        expected_document_ids={"jur-test-current"},
        expected_norm_related_document_ids={"jur-test-current"},
    )
    assert evaluation.passed is False
    assert evaluation.spurious_retrieval_rate > 0.0
