from datetime import date
from pathlib import Path

from app.domain.cbr import CBRReuseDecision
from app.domain.chunks import ChunkMetadata, LegalChunkType, LegalHierarchy
from app.domain.documents import SourceType
from app.domain.orchestration import (
    HybridOrchestrationRequest,
    OrchestrationStage,
    StageStatus,
)
from app.domain.query import ExtractedFact, QueryAnalysis, QueryIntent
from app.services.cbr_loader import load_cbr_cases_jsonl
from app.services.hybrid_orchestrator import HybridOrchestrator
from app.services.multidimensional_query_analysis import (
    analyze_query_multidimensional,
)
from app.services.primary_rbs_inventory import (
    load_current_production_rule_set,
)
from llm.providers.mock import MockLLMProvider
from llm.service import LlamaRAGService
from rag.retrieval.models import RetrievalHit, RetrievalResult
from tests.test_hybrid_orchestrator import FakeAnalyzer, FakeRetriever

ROOT = Path(__file__).resolve().parents[1]
CBR_CORPUS = ROOT / "cbr" / "data" / "production_cases.jsonl"
RBS_INVENTORY = ROOT / "app" / "resources" / "current_rbs_inventory.json"
RBS_DIR = ROOT / "rules" / "production"


def _professional_analysis() -> QueryAnalysis:
    query = (
        "Obligaciones de ISR de una persona fisica por "
        "servicios profesionales en 2026"
    )

    multidimensional = analyze_query_multidimensional(
        normalized_query=query,
        primary_intent=QueryIntent.IDENTIFY_OBLIGATIONS,
        secondary_intents=[],
        facts=[],
    )

    return QueryAnalysis(
        original_query=query,
        normalized_query=query,
        primary_intent=QueryIntent.IDENTIFY_OBLIGATIONS,
        facts=[
            ExtractedFact(
                name="taxpayer_type",
                value="individual",
            ),
            ExtractedFact(
                name="income_type",
                value="independent_professional_service",
            ),
            ExtractedFact(
                name="fiscal_year",
                value="2026",
            ),
        ],
        multidimensional=multidimensional,
        requires_clarification=False,
    )


def _lisr_retrieval() -> RetrievalResult:
    metadata = ChunkMetadata(
        document_id="lisr",
        source_type=SourceType.NORMATIVA,
        source_filename="LISR.pdf",
        chunk_index=0,
        chunk_type=LegalChunkType.ARTICLE,
        legal_identifier="Articulo 100",
        page_start=1,
        page_end=1,
        hierarchy=LegalHierarchy(article="Articulo 100"),
        source_sha256="a" * 64,
        fiscal_year=2026,
        version_label="2026",
        effective_from="2026-01-01",
        effective_to="2026-12-31",
    )

    return RetrievalResult(
        query=(
            "Obligaciones de ISR de una persona fisica por "
            "servicios profesionales en 2026"
        ),
        requested_top_k=5,
        candidate_count=1,
        returned_count=1,
        hits=[
            RetrievalHit(
                rank=1,
                score=0.99,
                chunk_id="lisr-articulo-100-test",
                text=(
                    "Articulo 100. Disposicion normativa aplicable "
                    "a ingresos por actividades empresariales y "
                    "servicios profesionales."
                ),
                metadata=metadata,
            )
        ],
    )


def test_production_cbr_case_is_recovered_through_orchestrator() -> None:
    cases = load_cbr_cases_jsonl(CBR_CORPUS)
    rule_set = load_current_production_rule_set(
        RBS_INVENTORY,
        RBS_DIR,
    )

    orchestrator = HybridOrchestrator(
        query_analyzer=FakeAnalyzer(_professional_analysis()),
        retriever=FakeRetriever(_lisr_retrieval()),
        llm_service=LlamaRAGService(MockLLMProvider()),
        rule_set=rule_set,
        cbr_cases=cases,
    )

    result = orchestrator.run(
        HybridOrchestrationRequest(
            query=(
                "Obligaciones de ISR de una persona fisica por "
                "servicios profesionales en 2026"
            ),
            query_date=date(2026, 9, 5),
            query_fiscal_year=2026,
            top_k=5,
            cbr_query=None,
        )
    )

    assert result.cbr_result is not None
    assert result.cbr_result.returned_count == 1

    match = result.cbr_result.matches[0]

    assert match.case_id == "CASE-TP-ISR-PROF-CUMPL-2026"
    assert match.similarity == 1.0

    assert len(result.cbr_reuse_assessments) == 1

    assessment = result.cbr_reuse_assessments[0]

    assert assessment.decision is CBRReuseDecision.ELIGIBLE
    assert assessment.shared_normative_refs == [
        "lisr:articulo_100"
    ]
    assert assessment.requires_human_review is False

    cbr_trace = next(
        trace
        for trace in result.traces
        if trace.stage == OrchestrationStage.CBR
    )

    assert cbr_trace.status is StageStatus.COMPLETED
    assert "Casos semejantes recuperados: 1" in cbr_trace.detail

    assert result.rbs_reasoning is not None
    assert result.cbr_reasoning is not None
    assert result.hybrid_coordination is not None
