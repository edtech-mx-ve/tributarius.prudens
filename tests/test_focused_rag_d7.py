from __future__ import annotations

from datetime import date

from app.domain.chunks import ChunkMetadata, LegalChunkType, LegalHierarchy
from app.domain.documents import SourceType
from app.domain.orchestration import HybridOrchestrationRequest, OrchestrationStage
from app.domain.query import FocusedRAGPlan, QueryAnalysis
from app.domain.rules import (
    RuleCondition,
    RuleDefinition,
    RuleOperator,
    RuleSet,
)
from app.services.focused_normative_rag import (
    execute_focused_rag,
    load_default_focused_rag_policy,
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


def _plan(query: str) -> FocusedRAGPlan:
    result = _analyze(query)
    assert result.focused_rag_plan is not None
    return result.focused_rag_plan


def _hit(
    *,
    chunk_id: str,
    document_id: str,
    score: float,
    source_type: SourceType = SourceType.NORMATIVA,
    legal_identifier: str = "Artículo 106",
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
            source_sha256="a" * 64,
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
            hits=[item.model_copy(update={"rank": rank}) for rank, item in enumerate(selected, 1)],
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
            hits=[item.model_copy(update={"rank": rank}) for rank, item in enumerate(selected, 1)],
        )


def _rules() -> RuleSet:
    return RuleSet(
        schema_version="1.0",
        rules=[
            RuleDefinition(
                rule_id="D7_TEST_RULE",
                version="1.0",
                description="Regla sintética que no debe controlar D.7.",
                conditions=[
                    RuleCondition(
                        fact="taxpayer_type",
                        operator=RuleOperator.EQ,
                        value="corporation",
                    )
                ],
                conclusion_code="d7_test",
                conclusion="Sin efecto material para la prueba D.7.",
            )
        ],
    )


def test_d7_professional_isr_builds_normative_focus_plan_from_d6() -> None:
    plan = _plan(
        "Soy persona física y presto servicios profesionales; "
        "quiero calcular ISR del ejercicio 2025."
    )
    policy = load_default_focused_rag_policy()

    assert plan.plan_applied is True
    assert plan.focus_source_ids[:2] == ["lisr", "cff"]
    assert "lisr:articulo_106" in plan.exact_normative_refs
    assert plan.normative_only is True
    assert plan.rag_retrieval_enabled is True
    assert plan.normative_text_retrieved is False
    assert plan.expansion_to_full_corpus_enabled is False
    assert plan.expansion_pending is True
    assert plan.allowed_chunk_types == policy.allowed_chunk_types
    assert len(plan.normative_corpus_ids) == 12


def test_d7_exact_article_seed_is_retrieved_before_semantic_hits() -> None:
    query = (
        "Soy persona física y presto servicios profesionales; "
        "quiero calcular ISR del ejercicio 2025."
    )
    plan = _plan(query)
    retriever = FilteringRetriever(
        [
            _hit(
                chunk_id="lisr-articulo-106",
                document_id="lisr",
                score=0.61,
                legal_identifier="Artículo 106",
            ),
            _hit(
                chunk_id="lisr-articulo-101",
                document_id="lisr",
                score=0.92,
                legal_identifier="Artículo 101",
            ),
            _hit(
                chunk_id="cff-articulo-1",
                document_id="cff",
                score=0.95,
                legal_identifier="Artículo 1",
            ),
        ]
    )

    run = execute_focused_rag(query, plan=plan, retriever=retriever, top_k=5)

    assert run.retrieval.hits[0].chunk_id == "lisr-articulo-106"
    assert run.retrieval.hits[0].score == 1.0
    assert "lisr-articulo-106" in run.execution.exact_seed_hit_ids
    assert run.execution.normative_text_retrieved is True
    assert run.execution.returned_count == run.retrieval.returned_count
    assert all(
        hit.metadata.source_type is SourceType.NORMATIVA for hit in run.retrieval.hits
    )
    assert set(run.execution.hit_source_ids).issubset(set(plan.focus_source_ids))


def test_d7_rejects_manual_and_wrong_target_hits_even_if_retriever_ignores_filters() -> None:
    query = (
        "Soy persona física y presto servicios profesionales; "
        "quiero calcular ISR del ejercicio 2025."
    )
    plan = _plan(query)
    retriever = IgnoringFiltersRetriever(
        [
            _hit(
                chunk_id="manual-prodecon",
                document_id="prodecon_contribuyente",
                score=0.99,
                source_type=SourceType.PRODECON,
                legal_identifier="PRODECON-11",
                chunk_type=LegalChunkType.SECTION,
            ),
            _hit(
                chunk_id="outside-liva",
                document_id="liva",
                score=0.98,
                legal_identifier="Artículo 1",
            ),
            _hit(
                chunk_id="lisr-valid",
                document_id="lisr",
                score=0.80,
                legal_identifier="Artículo 106",
            ),
        ]
    )

    run = execute_focused_rag(query, plan=plan, retriever=retriever, top_k=5)

    assert run.execution.rejected_non_normative_hits > 0
    assert run.execution.rejected_outside_focus_hits > 0
    assert all(hit.metadata.source_type is SourceType.NORMATIVA for hit in run.retrieval.hits)
    assert all(hit.metadata.document_id in plan.focus_source_ids for hit in run.retrieval.hits)
    assert "manual-prodecon" not in run.execution.hit_chunk_ids
    assert "outside-liva" not in run.execution.hit_chunk_ids


def test_d7_exact_seed_accepts_mexican_ordinal_article_label() -> None:
    query = (
        "El SAT me notificó un crédito fiscal y quiero impugnarlo "
        "mediante una defensa en 2026."
    )
    plan = _plan(query)
    retriever = FilteringRetriever(
        [
            _hit(
                chunk_id="lfdc-articulo-2-ordinal",
                document_id="lfdc",
                score=0.70,
                legal_identifier="Artículo 2o.",
            )
        ]
    )

    run = execute_focused_rag(query, plan=plan, retriever=retriever, top_k=5)

    assert "lfdc-articulo-2-ordinal" in run.execution.exact_seed_hit_ids
    assert run.retrieval.hits[0].score == 1.0


def test_d7_unknown_query_does_not_invent_rag_focus() -> None:
    plan = _plan("Necesito orientación sobre un asunto que no he descrito todavía.")

    assert plan.plan_applied is False
    assert plan.targets == []
    assert plan.focus_source_ids == []
    assert plan.rag_retrieval_enabled is False
    assert plan.normative_text_retrieved is False
    assert len(plan.normative_corpus_ids) == 12


def test_d7_rif_preserves_temporal_block_and_leaves_d9_pending() -> None:
    plan = _plan("¿Cómo calculaba ISR una persona física en RIF durante 2020?")

    assert plan.requires_temporal_validation is True
    assert plan.temporal_validation_completed is False
    assert "liva" in plan.temporal_blocked_source_ids
    assert plan.expansion_pending is True
    assert plan.can_control_legal_decision is False


def test_d7_orchestrator_uses_focused_normative_retrieval_when_plan_exists() -> None:
    query = (
        "Soy persona física y presto servicios profesionales; "
        "quiero calcular ISR del ejercicio 2025."
    )
    retriever = FilteringRetriever(
        [
            _hit(
                chunk_id="lisr-articulo-106-runtime",
                document_id="lisr",
                score=0.90,
                legal_identifier="Artículo 106",
            ),
            _hit(
                chunk_id="manual-unam-runtime",
                document_id="manual_derecho_fiscal_unam",
                score=0.99,
                source_type=SourceType.UNAM,
                legal_identifier="Capítulo V",
                chunk_type=LegalChunkType.CHAPTER,
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
    assert result.focused_rag_execution.retrieval_applied is True
    assert result.focused_rag_execution.normative_only is True
    assert result.retrieval.returned_count >= 1
    assert all(hit.metadata.source_type is SourceType.NORMATIVA for hit in result.retrieval.hits)
    retrieval_trace = next(
        item for item in result.traces if item.stage is OrchestrationStage.RETRIEVAL
    )
    assert "RAG focal D.7" in retrieval_trace.detail
