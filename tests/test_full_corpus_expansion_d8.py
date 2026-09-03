from __future__ import annotations

from datetime import date

from app.domain.chunks import ChunkMetadata, LegalChunkType, LegalHierarchy
from app.domain.documents import SourceType
from app.domain.orchestration import HybridOrchestrationRequest, OrchestrationStage
from app.domain.query import (
    FocusedRAGPlan,
    FullCorpusExpansionPlan,
    FullCorpusExpansionReason,
    QueryAnalysis,
)
from app.domain.rules import RuleCondition, RuleDefinition, RuleOperator, RuleSet
from app.services.focused_normative_rag import execute_focused_rag
from app.services.full_corpus_expansion import (
    execute_full_corpus_expansion,
    load_default_full_corpus_expansion_policy,
)
from app.services.hybrid_orchestrator import HybridOrchestrator
from llm.providers.mock import MockLLMProvider
from llm.providers.runtime_query import RuntimeQueryAnalyzerProvider
from llm.query_analyzer import QueryAnalyzer
from llm.service import LlamaRAGService
from rag.retrieval.filters import RetrievalFilters
from rag.retrieval.models import RetrievalHit, RetrievalResult


def _analyze(query: str) -> QueryAnalysis:
    return QueryAnalyzer(RuntimeQueryAnalyzerProvider()).analyze(query)


def _plans(query: str) -> tuple[FocusedRAGPlan, FullCorpusExpansionPlan]:
    result = _analyze(query)
    assert result.focused_rag_plan is not None
    assert result.full_corpus_expansion_plan is not None
    return result.focused_rag_plan, result.full_corpus_expansion_plan


def _hit(
    *,
    chunk_id: str,
    document_id: str,
    score: float,
    legal_identifier: str = "Artículo 106",
    source_type: SourceType = SourceType.NORMATIVA,
    chunk_type: LegalChunkType = LegalChunkType.ARTICLE,
) -> RetrievalHit:
    return RetrievalHit(
        rank=1,
        score=score,
        chunk_id=chunk_id,
        text=f"Contenido jurídico de {document_id} {legal_identifier}.",
        metadata=ChunkMetadata(
            document_id=document_id,
            canonical_id=document_id,
            source_type=source_type,
            source_filename=f"{document_id}.md",
            chunk_index=1,
            chunk_type=chunk_type,
            legal_identifier=legal_identifier,
            source_unit_label=legal_identifier,
            hierarchy=LegalHierarchy(article=legal_identifier),
            source_sha256="b" * 64,
            version_label="2025",
        ),
    )


class FilteringRetriever:
    def __init__(self, hits: list[RetrievalHit]) -> None:
        self.hits = hits
        self.calls: list[RetrievalFilters | None] = []

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> RetrievalResult:
        self.calls.append(filters)
        active = filters or RetrievalFilters()
        eligible = [
            hit
            for hit in self.hits
            if active.matches(
                source_type=hit.metadata.source_type,
                chunk_type=hit.metadata.chunk_type,
                fiscal_year=hit.metadata.fiscal_year,
                version_label=hit.metadata.version_label,
                document_id=hit.metadata.document_id,
                legal_identifier=hit.metadata.legal_identifier,
            )
        ]
        eligible.sort(key=lambda item: (-item.score, item.chunk_id))
        selected = eligible[:top_k]
        return RetrievalResult(
            query=query,
            requested_top_k=top_k,
            candidate_count=len(eligible),
            returned_count=len(selected),
            hits=[
                item.model_copy(update={"rank": rank})
                for rank, item in enumerate(selected, start=1)
            ],
        )


class IgnoringFiltersRetriever:
    def __init__(self, hits: list[RetrievalHit]) -> None:
        self.hits = hits

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> RetrievalResult:
        del filters
        selected = self.hits[:top_k]
        return RetrievalResult(
            query=query,
            requested_top_k=top_k,
            candidate_count=len(self.hits),
            returned_count=len(selected),
            hits=[
                item.model_copy(update={"rank": rank})
                for rank, item in enumerate(selected, start=1)
            ],
        )


def _rules() -> RuleSet:
    return RuleSet(
        schema_version="1.0",
        rules=[
            RuleDefinition(
                rule_id="D8_TEST_RULE",
                version="1.0",
                description="Regla sintética sin autoridad sobre la expansión D.8.",
                conditions=[
                    RuleCondition(
                        fact="taxpayer_type",
                        operator=RuleOperator.EQ,
                        value="corporation",
                    )
                ],
                conclusion_code="d8_test",
                conclusion="Sin efecto material para la prueba D.8.",
            )
        ],
    )


def test_d8_plan_preserves_focus_and_completes_exactly_twelve_corpora() -> None:
    focused, expansion = _plans(
        "Soy persona física y presto servicios profesionales; "
        "quiero calcular ISR del ejercicio 2025."
    )
    policy = load_default_full_corpus_expansion_policy()

    assert expansion.plan_applied is True
    assert expansion.focus_source_ids == focused.focus_source_ids
    assert set(expansion.focus_source_ids).isdisjoint(expansion.expansion_source_ids)
    assert set(expansion.focus_source_ids) | set(expansion.expansion_source_ids) == set(
        expansion.normative_corpus_ids
    )
    assert len(expansion.normative_corpus_ids) == 12
    assert len(expansion.source_relevance_scores) == 12
    assert expansion.minimum_focused_hits == policy.minimum_focused_hits
    assert expansion.expansion_to_full_corpus_enabled is True
    assert expansion.source_exclusion_enabled is False


def test_d8_skips_expansion_when_focused_retrieval_is_sufficient() -> None:
    query = (
        "Soy persona física y presto servicios profesionales; "
        "quiero calcular ISR del ejercicio 2025."
    )
    focused_plan, expansion_plan = _plans(query)
    retriever = FilteringRetriever(
        [
            _hit(
                chunk_id="lisr-106",
                document_id="lisr",
                score=0.95,
                legal_identifier="Artículo 106",
            ),
            _hit(
                chunk_id="lisr-101",
                document_id="lisr",
                score=0.91,
                legal_identifier="Artículo 101",
            ),
            _hit(
                chunk_id="cff-1",
                document_id="cff",
                score=0.90,
                legal_identifier="Artículo 1",
            ),
        ]
    )
    focused_run = execute_focused_rag(
        query,
        plan=focused_plan,
        retriever=retriever,
        top_k=5,
    )
    run = execute_full_corpus_expansion(
        query,
        plan=expansion_plan,
        retriever=retriever,
        top_k=5,
        focused_retrieval=focused_run.retrieval,
        focused_execution=focused_run.execution,
    )

    assert focused_run.execution.returned_count >= 3
    assert len(focused_run.execution.hit_source_ids) >= 2
    assert run.execution.expansion_applied is False
    assert run.execution.trigger_reasons == []
    assert run.execution.searched_expansion_source_ids == []
    assert run.retrieval == focused_run.retrieval
    assert run.execution.full_corpus_search_coverage_complete is False


def test_d8_expands_remaining_corpora_when_focused_hits_are_insufficient() -> None:
    query = (
        "Soy persona física y presto servicios profesionales; "
        "quiero calcular ISR del ejercicio 2025."
    )
    focused_plan, expansion_plan = _plans(query)
    retriever = FilteringRetriever(
        [
            _hit(
                chunk_id="lisr-106-exact",
                document_id="lisr",
                score=0.80,
                legal_identifier="Artículo 106",
            ),
            _hit(
                chunk_id="lfdc-2-expansion",
                document_id="lfdc",
                score=0.99,
                legal_identifier="Artículo 2",
            ),
            _hit(
                chunk_id="lfpca-1-expansion",
                document_id="lfpca",
                score=0.97,
                legal_identifier="Artículo 1",
            ),
        ]
    )
    focused_run = execute_focused_rag(
        query,
        plan=focused_plan,
        retriever=retriever,
        top_k=5,
    )
    run = execute_full_corpus_expansion(
        query,
        plan=expansion_plan,
        retriever=retriever,
        top_k=5,
        focused_retrieval=focused_run.retrieval,
        focused_execution=focused_run.execution,
    )

    assert run.execution.expansion_applied is True
    assert FullCorpusExpansionReason.INSUFFICIENT_FOCUSED_HITS in run.execution.trigger_reasons
    assert run.execution.searched_expansion_source_ids == expansion_plan.expansion_source_ids
    assert run.execution.full_corpus_search_coverage_complete is True
    assert run.retrieval.hits[0].chunk_id == "lisr-106-exact"
    assert "lfdc-2-expansion" in run.execution.expansion_hit_chunk_ids
    assert set(run.execution.hit_source_ids).issubset(set(expansion_plan.normative_corpus_ids))


def test_d8_unknown_query_uses_all_twelve_normative_corpora_as_fallback() -> None:
    query = "Necesito orientación sobre un asunto que no he descrito todavía."
    focused_plan, expansion_plan = _plans(query)
    retriever = FilteringRetriever(
        [
            _hit(
                chunk_id="cff-fallback",
                document_id="cff",
                score=0.88,
                legal_identifier="Artículo 1",
            )
        ]
    )

    assert focused_plan.plan_applied is False
    assert expansion_plan.focus_source_ids == []
    assert len(expansion_plan.expansion_source_ids) == 12

    run = execute_full_corpus_expansion(
        query,
        plan=expansion_plan,
        retriever=retriever,
        top_k=5,
    )

    assert run.execution.expansion_applied is True
    assert run.execution.trigger_reasons == [FullCorpusExpansionReason.NO_FOCUSED_PLAN]
    assert len(run.execution.searched_expansion_source_ids) == 12
    assert run.execution.full_corpus_search_coverage_complete is True
    assert run.retrieval.hits[0].metadata.document_id == "cff"
    assert run.retrieval.hits[0].metadata.source_type is SourceType.NORMATIVA


def test_d8_rejects_non_normative_and_outside_corpus_hits() -> None:
    query = "Necesito orientación sobre un asunto que no he descrito todavía."
    _, expansion_plan = _plans(query)
    retriever = IgnoringFiltersRetriever(
        [
            _hit(
                chunk_id="manual-prodecon-d8",
                document_id="prodecon_contribuyente",
                score=0.99,
                source_type=SourceType.PRODECON,
                chunk_type=LegalChunkType.SECTION,
                legal_identifier="PRODECON-07",
            ),
            _hit(
                chunk_id="outside-d8",
                document_id="norma_fuera_a8",
                score=0.98,
                legal_identifier="Artículo 1",
            ),
        ]
    )

    run = execute_full_corpus_expansion(
        query,
        plan=expansion_plan,
        retriever=retriever,
        top_k=5,
    )

    assert run.execution.rejected_non_normative_hits > 0
    assert run.execution.rejected_outside_corpus_hits > 0
    assert run.retrieval.returned_count == 0
    assert run.execution.normative_only is True
    assert run.execution.can_control_legal_decision is False


def test_d8_rif_keeps_temporal_validation_pending_for_d9() -> None:
    _, expansion_plan = _plans("¿Cómo calculaba ISR una persona física en RIF durante 2020?")

    assert "liva" in expansion_plan.temporal_blocked_source_ids
    assert expansion_plan.requires_temporal_validation is True
    assert expansion_plan.temporal_validation_completed is False
    assert expansion_plan.can_control_legal_decision is False


def test_d8_orchestrator_expands_when_d7_focus_is_insufficient() -> None:
    query = (
        "Soy persona física y presto servicios profesionales; "
        "quiero calcular ISR del ejercicio 2025."
    )
    retriever = FilteringRetriever(
        [
            _hit(
                chunk_id="lisr-106-runtime-d8",
                document_id="lisr",
                score=0.90,
                legal_identifier="Artículo 106",
            ),
            _hit(
                chunk_id="lfdc-2-runtime-d8",
                document_id="lfdc",
                score=0.98,
                legal_identifier="Artículo 2",
            ),
        ]
    )
    service = HybridOrchestrator(
        query_analyzer=QueryAnalyzer(RuntimeQueryAnalyzerProvider()),
        retriever=retriever,
        llm_service=LlamaRAGService(MockLLMProvider()),
        rule_set=_rules(),
    )

    result = service.run(
        HybridOrchestrationRequest(
            query=query,
            query_date=date(2026, 9, 3),
            query_fiscal_year=2025,
            top_k=5,
        )
    )

    assert result.focused_rag_execution is not None
    assert result.full_corpus_expansion_execution is not None
    assert result.full_corpus_expansion_execution.expansion_applied is True
    assert result.full_corpus_expansion_execution.full_corpus_search_coverage_complete is True
    assert all(hit.metadata.source_type is SourceType.NORMATIVA for hit in result.retrieval.hits)
    retrieval_trace = next(
        item for item in result.traces if item.stage is OrchestrationStage.RETRIEVAL
    )
    assert "expansión D.8" in retrieval_trace.detail
