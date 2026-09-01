from datetime import date
from decimal import Decimal

from app.domain.cbr import CaseStatus, CBRCase, CBRQuery
from app.domain.chunks import ChunkMetadata, LegalChunkType, LegalHierarchy
from app.domain.documents import SourceType
from app.domain.isr import (
    ISRBracket,
    ISRCalculationInput,
    ISRPeriod,
    ISRTariff,
)
from app.domain.orchestration import (
    HybridOrchestrationRequest,
    NormativeCandidate,
    OrchestrationStage,
    StageStatus,
)
from app.domain.query import ExtractedFact, QueryAnalysis, QueryIntent
from app.domain.rules import RuleCondition, RuleDefinition, RuleOperator, RuleSet
from app.services.hybrid_orchestrator import HybridOrchestrator, build_fact_map
from llm.providers.mock import MockLLMProvider
from llm.service import LlamaRAGService
from rag.retrieval.filters import RetrievalFilters
from rag.retrieval.models import RetrievalHit, RetrievalResult


class FakeAnalyzer:
    def __init__(self, analysis: QueryAnalysis) -> None:
        self._analysis = analysis

    def analyze(self, query: str) -> QueryAnalysis:
        del query
        return self._analysis


class FakeRetriever:
    def __init__(self, result: RetrievalResult) -> None:
        self._result = result
        self.last_filters: RetrievalFilters | None = None

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> RetrievalResult:
        del query, top_k
        self.last_filters = filters
        return self._result


def analysis(
    *,
    intent: QueryIntent = QueryIntent.CALCULATE_ISR,
    jurisprudence_requested: bool = False,
    requires_clarification: bool = False,
) -> QueryAnalysis:
    return QueryAnalysis(
        original_query="Calcula ISR",
        normalized_query="Calcula ISR",
        primary_intent=intent,
        facts=[
            ExtractedFact(name="fiscal_year", value="2026"),
            ExtractedFact(name="taxpayer_type", value="individual"),
        ],
        jurisprudence_requested=jurisprudence_requested,
        requires_clarification=requires_clarification,
    )


def retrieval() -> RetrievalResult:
    metadata = ChunkMetadata(
        document_id="normativa-test",
        source_type=SourceType.NORMATIVA,
        source_filename="norma.md",
        chunk_index=0,
        chunk_type=LegalChunkType.ARTICLE,
        legal_identifier="Artículo test",
        page_start=1,
        page_end=1,
        hierarchy=LegalHierarchy(article="Artículo test"),
        source_sha256="a" * 64,
        fiscal_year=2026,
        version_label="2026-A",
    )
    return RetrievalResult(
        query="Calcula ISR",
        requested_top_k=5,
        candidate_count=1,
        returned_count=1,
        hits=[
            RetrievalHit(
                rank=1,
                score=0.95,
                chunk_id="normativa-test-chunk-00001",
                text="Evidencia normativa sintética de prueba.",
                metadata=metadata,
            )
        ],
    )


def rules() -> RuleSet:
    return RuleSet(
        schema_version="1.0",
        rules=[
            RuleDefinition(
                rule_id="ISR_RULE_001",
                version="1.0",
                description="Regla sintética.",
                conditions=[
                    RuleCondition(
                        fact="taxpayer_type",
                        operator=RuleOperator.EQ,
                        value="individual",
                    )
                ],
                conclusion_code="isr_profile",
                conclusion="Perfil sujeto a revisión ISR.",
                normative_refs=["NORM_TEST_ISR_2026"],
            )
        ],
    )


def tariff() -> ISRTariff:
    return ISRTariff(
        schema_version="1.0",
        version="TEST-1.0",
        fiscal_year=2026,
        period=ISRPeriod.ANNUAL,
        normative_ref="NORM_TEST_ISR_2026",
        source_reference="FIXTURE_ONLY",
        verified=True,
        brackets=[
            ISRBracket(
                lower_limit=Decimal("0"),
                upper_limit=Decimal("10000"),
                fixed_fee=Decimal("0"),
                rate_percent=Decimal("10"),
            ),
            ISRBracket(
                lower_limit=Decimal("10000.01"),
                upper_limit=None,
                fixed_fee=Decimal("1000"),
                rate_percent=Decimal("20"),
            ),
        ],
    )


def isr_input() -> ISRCalculationInput:
    return ISRCalculationInput(
        fiscal_year=2026,
        period=ISRPeriod.ANNUAL,
        gross_income=Decimal("20000"),
        exempt_income=Decimal("1000"),
        authorized_deductions=Decimal("2000"),
        credits=Decimal("100"),
        normative_ref="NORM_TEST_ISR_2026",
    )


def candidate() -> NormativeCandidate:
    return NormativeCandidate(
        ref="NORM_TEST_ISR_2026",
        legal_unit_id=1,
        version_label="2026-A",
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 12, 31),
        fiscal_year=2026,
    )


def orchestrator(
    fake_retriever: FakeRetriever,
    query_analysis: QueryAnalysis,
) -> HybridOrchestrator:
    return HybridOrchestrator(
        query_analyzer=FakeAnalyzer(query_analysis),
        retriever=fake_retriever,
        llm_service=LlamaRAGService(MockLLMProvider()),
        rule_set=rules(),
        isr_tariff=tariff(),
    )


def test_end_to_end_hybrid_flow() -> None:
    fake_retriever = FakeRetriever(retrieval())
    service = orchestrator(fake_retriever, analysis())
    result = service.run(
        HybridOrchestrationRequest(
            query="Calcula ISR",
            query_date=date(2026, 8, 28),
            query_fiscal_year=2026,
            normative_candidates=[candidate()],
            isr_input=isr_input(),
        )
    )

    assert result.applicable_normative_refs == ["NORM_TEST_ISR_2026"]
    assert result.rule_result.matched_rules[0].rule_id == "ISR_RULE_001"
    assert result.isr_result is not None
    assert result.isr_result.final_tax == Decimal("2300.00")
    assert result.explanation is not None
    assert result.explanation.generation_performed is True
    assert result.requires_human_review is False


def test_default_retrieval_excludes_jurisprudence() -> None:
    fake_retriever = FakeRetriever(retrieval())
    service = orchestrator(fake_retriever, analysis())
    service.run(
        HybridOrchestrationRequest(
            query="Calcula ISR",
            query_date=date(2026, 8, 28),
        )
    )
    assert fake_retriever.last_filters is not None
    assert SourceType.JURISPRUDENCIA not in fake_retriever.last_filters.source_types


def test_explicit_jurisprudence_request_stays_out_of_primary_retriever() -> None:
    fake_retriever = FakeRetriever(retrieval())
    service = orchestrator(
        fake_retriever,
        analysis(
            intent=QueryIntent.RELATED_JURISPRUDENCE,
            jurisprudence_requested=True,
        ),
    )
    result = service.run(
        HybridOrchestrationRequest(
            query="Busca jurisprudencia",
            query_date=date(2026, 8, 28),
        )
    )
    assert fake_retriever.last_filters is not None
    assert SourceType.JURISPRUDENCIA not in fake_retriever.last_filters.source_types
    assert result.jurisprudence_result is None
    assert result.requires_human_review is True


def test_isr_is_blocked_without_applicable_norm() -> None:
    fake_retriever = FakeRetriever(retrieval())
    service = orchestrator(fake_retriever, analysis())
    result = service.run(
        HybridOrchestrationRequest(
            query="Calcula ISR",
            query_date=date(2026, 8, 28),
            query_fiscal_year=2026,
            isr_input=isr_input(),
        )
    )
    assert result.isr_result is None
    assert result.requires_human_review is True
    isr_trace = next(
        item for item in result.traces if item.stage == OrchestrationStage.ISR
    )
    assert isr_trace.status == StageStatus.SKIPPED


def test_missing_required_data_blocks_isr() -> None:
    fake_retriever = FakeRetriever(retrieval())
    service = orchestrator(
        fake_retriever,
        analysis(requires_clarification=True),
    )
    result = service.run(
        HybridOrchestrationRequest(
            query="Calcula ISR",
            query_date=date(2026, 8, 28),
            query_fiscal_year=2026,
            normative_candidates=[candidate()],
            isr_input=isr_input(),
        )
    )
    assert result.isr_result is None
    assert result.requires_human_review is True


def test_fact_map_only_coerces_known_fiscal_year() -> None:
    mapped = build_fact_map(analysis())
    assert mapped["fiscal_year"] == 2026
    assert mapped["taxpayer_type"] == "individual"


def test_cbr_is_integrated_without_overriding_normative_flow() -> None:
    fake_retriever = FakeRetriever(retrieval())
    service = HybridOrchestrator(
        query_analyzer=FakeAnalyzer(analysis()),
        retriever=fake_retriever,
        llm_service=LlamaRAGService(MockLLMProvider()),
        rule_set=rules(),
        isr_tariff=tariff(),
        cbr_cases=[
            CBRCase(
                case_id="CASE-CBR-001",
                status=CaseStatus.ACTIVE,
                taxpayer_type="individual",
                activity="servicios profesionales",
                tax="ISR",
                problem_type="determinacion de obligaciones",
                procedural_stage="orientacion",
                fiscal_year=2026,
                resolution_summary="Caso sintético semejante.",
                normative_refs=["NORM_TEST_ISR_2026"],
                source_refs=["CBR_TEST"],
            )
        ],
    )
    result = service.run(
        HybridOrchestrationRequest(
            query="Calcula ISR",
            query_date=date(2026, 8, 28),
            query_fiscal_year=2026,
            normative_candidates=[candidate()],
            isr_input=isr_input(),
            cbr_query=CBRQuery(
                taxpayer_type="individual",
                activity="servicios profesionales",
                tax="ISR",
                problem_type="determinacion de obligaciones",
                procedural_stage="orientacion",
                fiscal_year=2026,
            ),
        )
    )

    assert result.cbr_result is not None
    assert result.cbr_result.matches[0].case_id == "CASE-CBR-001"
    assert result.applicable_normative_refs == ["NORM_TEST_ISR_2026"]
    assert result.isr_result is not None
    assert result.isr_result.final_tax == Decimal("2300.00")
