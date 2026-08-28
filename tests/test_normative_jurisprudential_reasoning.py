from datetime import date
from pathlib import Path

from app.domain.chunks import ChunkMetadata, LegalChunkType, LegalHierarchy
from app.domain.documents import SourceType
from app.domain.orchestration import (
    HybridOrchestrationRequest,
    OrchestrationStage,
    StageStatus,
)
from app.domain.query import QueryAnalysis, QueryIntent
from app.services.hybrid_orchestrator import HybridOrchestrator
from app.services.traceability import build_canonical_result, verify_canonical_integrity
from jurisprudence.loader import load_jurisprudence_metadata
from jurisprudence.retrieval import JurisprudenceRetriever
from llm.providers.mock import MockLLMProvider
from llm.service import LlamaRAGService
from rag.retrieval.models import RetrievalHit, RetrievalResult
from tests.test_hybrid_orchestrator import (
    FakeAnalyzer,
    FakeRetriever,
    candidate,
    retrieval,
    rules,
)


class JurisprudenceFakeRetriever:
    def __init__(self, document_ids: list[str]) -> None:
        self.document_ids = document_ids
        self.last_filters = None

    def search(self, query: str, *, top_k: int = 5, filters=None) -> RetrievalResult:
        del top_k
        self.last_filters = filters
        hits = []
        for rank, document_id in enumerate(self.document_ids, start=1):
            metadata = ChunkMetadata(
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
            hits.append(
                RetrievalHit(
                    rank=rank,
                    score=0.93,
                    chunk_id=f"{document_id}-chunk-0001",
                    text="Criterio jurisprudencial sintético de prueba.",
                    metadata=metadata,
                )
            )
        return RetrievalResult(
            query=query,
            requested_top_k=5,
            candidate_count=len(hits),
            returned_count=len(hits),
            hits=hits,
        )


def jurisprudential_analysis() -> QueryAnalysis:
    return QueryAnalysis(
        original_query="Interpreta la disposición y muestra jurisprudencia relacionada.",
        normalized_query="Interpreta la disposición y muestra jurisprudencia relacionada.",
        primary_intent=QueryIntent.INTERPRET_PROVISION,
        jurisprudence_requested=True,
    )


def service(document_ids: list[str]) -> tuple[HybridOrchestrator, JurisprudenceFakeRetriever]:
    raw_jurisprudence = JurisprudenceFakeRetriever(document_ids)
    registry = load_jurisprudence_metadata(
        Path("jurisprudence/fixtures/metadata_synthetic.jsonl")
    )
    jurisprudence = JurisprudenceRetriever(raw_jurisprudence, registry)
    hybrid = HybridOrchestrator(
        query_analyzer=FakeAnalyzer(jurisprudential_analysis()),
        retriever=FakeRetriever(retrieval()),
        llm_service=LlamaRAGService(MockLLMProvider()),
        rule_set=rules(),
        jurisprudence_retriever=jurisprudence,
    )
    return hybrid, raw_jurisprudence


def request() -> HybridOrchestrationRequest:
    return HybridOrchestrationRequest(
        query="Interpreta la disposición y muestra jurisprudencia relacionada.",
        query_date=date(2026, 8, 28),
        query_fiscal_year=2026,
        normative_candidates=[candidate()],
    )


def test_jurisprudence_runs_after_normative_applicability() -> None:
    hybrid, raw_jurisprudence = service(["jur-test-current"])
    result = hybrid.run(request())

    assert result.applicable_normative_refs == ["NORM_TEST_ISR_2026"]
    assert result.jurisprudence_result is not None
    assert result.jurisprudence_result.returned_count == 1
    assert result.jurisprudence_result.hits[0].assessment.relevant_to_norm is True
    assert raw_jurisprudence.last_filters.source_types == {SourceType.JURISPRUDENCIA}

    stages = [item.stage for item in result.traces]
    assert stages.index(OrchestrationStage.NORMATIVE) < stages.index(
        OrchestrationStage.JURISPRUDENCE
    )


def test_historical_jurisprudence_propagates_human_review() -> None:
    hybrid, _ = service(["jur-test-historical"])
    result = hybrid.run(request())

    assert result.jurisprudence_result is not None
    assert result.jurisprudence_result.requires_human_review is True
    assert result.requires_human_review is True


def test_superseded_jurisprudence_never_changes_applicable_norms() -> None:
    hybrid, _ = service(["jur-test-superseded"])
    result = hybrid.run(request())

    assert result.applicable_normative_refs == ["NORM_TEST_ISR_2026"]
    assert result.jurisprudence_result is not None
    assert result.jurisprudence_result.returned_count == 0


def test_canonical_trace_has_separate_jurisprudential_sources() -> None:
    hybrid, _ = service(["jur-test-current"])
    req = request()
    result = hybrid.run(req)
    canonical = build_canonical_result(req, result)

    assert canonical.jurisprudence is not None
    assert len(canonical.traceability.jurisprudential_sources) == 1
    source = canonical.traceability.jurisprudential_sources[0]
    assert source.kind.value == "jurisprudence"
    assert source.ref_id == "jur-test-current-chunk-0001"
    assert verify_canonical_integrity(canonical) is True


def test_jurisprudence_event_references_only_jurisprudential_chunks() -> None:
    hybrid, _ = service(["jur-test-current"])
    req = request()
    canonical = build_canonical_result(req, hybrid.run(req))
    event = next(
        item
        for item in canonical.traceability.events
        if item.stage == "jurisprudence"
    )
    assert event.evidence_refs == ["jur-test-current-chunk-0001"]


def test_missing_jurisprudence_retriever_degrades_without_losing_normative_result() -> None:
    hybrid = HybridOrchestrator(
        query_analyzer=FakeAnalyzer(jurisprudential_analysis()),
        retriever=FakeRetriever(retrieval()),
        llm_service=LlamaRAGService(MockLLMProvider()),
        rule_set=rules(),
    )
    result = hybrid.run(request())

    assert result.applicable_normative_refs == ["NORM_TEST_ISR_2026"]
    assert result.jurisprudence_result is None
    assert result.requires_human_review is True
    event = next(
        item for item in result.traces if item.stage == OrchestrationStage.JURISPRUDENCE
    )
    assert event.status == StageStatus.DEGRADED


def test_llm_receives_jurisprudence_as_structured_deterministic_context() -> None:
    hybrid, _ = service(["jur-test-current"])
    result = hybrid.run(request())

    assert result.explanation is not None
    # Mock provider accepts the structured contract; jurisprudence is not merged
    # into the primary retrieval evidence and therefore cannot masquerade as normativa.
    assert all(
        hit.metadata.source_type != SourceType.JURISPRUDENCIA
        for hit in result.retrieval.hits
    )
