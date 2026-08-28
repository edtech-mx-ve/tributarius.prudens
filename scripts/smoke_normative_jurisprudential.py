from __future__ import annotations

from datetime import date
from pathlib import Path

from app.domain.chunks import ChunkMetadata, LegalChunkType, LegalHierarchy
from app.domain.documents import SourceType
from app.domain.orchestration import HybridOrchestrationRequest
from app.domain.query import QueryAnalysis, QueryIntent
from app.services.hybrid_orchestrator import HybridOrchestrator
from app.services.traceability import build_canonical_result, verify_canonical_integrity
from jurisprudence.loader import load_jurisprudence_metadata
from jurisprudence.retrieval import JurisprudenceRetriever
from llm.providers.mock import MockLLMProvider
from llm.service import LlamaRAGService
from rag.retrieval.filters import RetrievalFilters
from rag.retrieval.models import RetrievalHit, RetrievalResult
from tests.test_hybrid_orchestrator import (
    FakeAnalyzer,
    FakeRetriever,
    candidate,
    retrieval,
    rules,
)


class SyntheticJurisprudenceRetriever:
    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> RetrievalResult:
        del top_k, filters
        metadata = ChunkMetadata(
            document_id="jur-test-current",
            source_type=SourceType.JURISPRUDENCIA,
            source_filename="jur-test-current.md",
            chunk_index=0,
            chunk_type=LegalChunkType.PARAGRAPH,
            legal_identifier="SYN-JUR-001",
            page_start=1,
            page_end=1,
            hierarchy=LegalHierarchy(),
            source_sha256="a" * 64,
        )
        return RetrievalResult(
            query=query,
            requested_top_k=5,
            candidate_count=1,
            returned_count=1,
            hits=[
                RetrievalHit(
                    rank=1,
                    score=0.93,
                    chunk_id="jur-test-current-chunk-0001",
                    text="Criterio jurisprudencial sintético.",
                    metadata=metadata,
                )
            ],
        )


def main() -> int:
    registry = load_jurisprudence_metadata(
        Path("jurisprudence/fixtures/metadata_synthetic.jsonl")
    )
    analysis = QueryAnalysis(
        original_query="Interpreta la norma y muestra jurisprudencia.",
        normalized_query="Interpreta la norma y muestra jurisprudencia.",
        primary_intent=QueryIntent.INTERPRET_PROVISION,
        jurisprudence_requested=True,
    )
    hybrid = HybridOrchestrator(
        query_analyzer=FakeAnalyzer(analysis),
        retriever=FakeRetriever(retrieval()),
        llm_service=LlamaRAGService(MockLLMProvider()),
        rule_set=rules(),
        jurisprudence_retriever=JurisprudenceRetriever(
            SyntheticJurisprudenceRetriever(),
            registry,
        ),
    )
    request = HybridOrchestrationRequest(
        query=analysis.original_query,
        query_date=date(2026, 8, 28),
        query_fiscal_year=2026,
        normative_candidates=[candidate()],
    )
    result = hybrid.run(request)
    canonical = build_canonical_result(request, result)

    ok = (
        result.applicable_normative_refs == ["NORM_TEST_ISR_2026"]
        and result.jurisprudence_result is not None
        and result.jurisprudence_result.returned_count == 1
        and len(canonical.traceability.jurisprudential_sources) == 1
        and verify_canonical_integrity(canonical)
    )
    if not ok:
        print("ERROR: smoke normativo-jurisprudencial inválido.")
        return 1
    print(
        "OK: norma aplicable=1; jurisprudencia elegible=1; "
        "trazabilidad separada=1; integridad=True."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
