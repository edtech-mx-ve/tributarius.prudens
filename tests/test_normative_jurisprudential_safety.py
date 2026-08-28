from datetime import date
from pathlib import Path

from app.domain.orchestration import HybridOrchestrationRequest
from app.domain.query import QueryAnalysis, QueryIntent
from app.services.hybrid_orchestrator import HybridOrchestrator
from jurisprudence.loader import load_jurisprudence_metadata
from jurisprudence.retrieval import JurisprudenceRetriever
from llm.providers.mock import MockLLMProvider
from llm.service import LlamaRAGService
from tests.test_hybrid_orchestrator import (
    FakeAnalyzer,
    FakeRetriever,
    candidate,
    retrieval,
    rules,
)
from tests.test_normative_jurisprudential_reasoning import JurisprudenceFakeRetriever


class BrokenJurisprudenceRetriever:
    def search(self, *args, **kwargs):
        del args, kwargs
        from jurisprudence.retrieval import JurisprudenceRetrievalError

        raise JurisprudenceRetrievalError("fallo sintético")


def explicit_analysis() -> QueryAnalysis:
    return QueryAnalysis(
        original_query="Busca jurisprudencia relacionada.",
        normalized_query="Busca jurisprudencia relacionada.",
        primary_intent=QueryIntent.RELATED_JURISPRUDENCE,
        jurisprudence_requested=True,
    )


def test_jurisprudential_failure_preserves_normative_result() -> None:
    hybrid = HybridOrchestrator(
        query_analyzer=FakeAnalyzer(explicit_analysis()),
        retriever=FakeRetriever(retrieval()),
        llm_service=LlamaRAGService(MockLLMProvider()),
        rule_set=rules(),
        jurisprudence_retriever=BrokenJurisprudenceRetriever(),
    )
    result = hybrid.run(
        HybridOrchestrationRequest(
            query="Busca jurisprudencia relacionada.",
            query_date=date(2026, 8, 28),
            query_fiscal_year=2026,
            normative_candidates=[candidate()],
        )
    )
    assert result.applicable_normative_refs == ["NORM_TEST_ISR_2026"]
    assert result.jurisprudence_result is None
    assert result.requires_human_review is True


def test_jurisprudential_registry_cannot_turn_norm_into_jurisprudence() -> None:
    registry = load_jurisprudence_metadata(
        Path("jurisprudence/fixtures/metadata_synthetic.jsonl")
    )
    raw = JurisprudenceFakeRetriever(["jur-test-current"])
    service = JurisprudenceRetriever(raw, registry)
    assert set(registry) == {
        "jur-test-current",
        "jur-test-historical",
        "jur-test-superseded",
    }
    assert all(item.source_reference == "FIXTURE_ONLY" for item in registry.values())
    assert service is not None
