from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.domain.chunks import ChunkMetadata, LegalChunkType, LegalHierarchy
from app.domain.documents import SourceType
from app.domain.isr import (
    ISRBracket,
    ISRCalculationInput,
    ISRPeriod,
    ISRTariff,
    ISRTariffLegalMetadata,
)
from app.domain.normative import NormativeValidityStatus
from app.domain.orchestration import (
    HybridOrchestrationRequest,
    NormativeCandidate,
    OrchestrationStage,
    StageStatus,
)
from app.domain.query import ExtractedFact, QueryAnalysis, QueryIntent
from app.domain.rules import RuleCondition, RuleDefinition, RuleOperator, RuleSet
from app.services.hybrid_orchestrator import HybridOrchestrator
from calculators.isr_tariff_registry import ISRTariffRegistry
from llm.providers.mock import MockLLMProvider
from llm.service import LlamaRAGService
from rag.retrieval.filters import RetrievalFilters
from rag.retrieval.models import RetrievalHit, RetrievalResult

ARTICLE_100_CHUNK = "lisr-article-100"
ARTICLE_152_CHUNK = "lisr-article-152"
ARTICLE_100_REF = "lisr:articulo_100"
ARTICLE_152_REF = "lisr:articulo_152"


class FakeAnalyzer:
    def analyze(self, query: str) -> QueryAnalysis:
        return QueryAnalysis(
            original_query=query,
            normalized_query=query,
            primary_intent=QueryIntent.CALCULATE_ISR,
            facts=[
                ExtractedFact(name="fiscal_year", value="2026"),
                ExtractedFact(name="taxpayer_type", value="individual"),
                ExtractedFact(
                    name="income_type",
                    value="independent_professional_services",
                ),
            ],
        )


class FakeRetriever:
    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> RetrievalResult:
        del top_k, filters
        hits = [
            _hit(1, ARTICLE_100_CHUNK, "Artículo 100"),
            _hit(2, ARTICLE_152_CHUNK, "Artículo 152"),
        ]
        return RetrievalResult(
            query=query,
            requested_top_k=5,
            candidate_count=2,
            returned_count=2,
            hits=hits,
        )


def _hit(rank: int, chunk_id: str, article: str) -> RetrievalHit:
    return RetrievalHit(
        rank=rank,
        score=0.99,
        chunk_id=chunk_id,
        text=f"{article}. Evidencia normativa ISR controlada.",
        metadata=ChunkMetadata(
            document_id="lisr",
            source_type=SourceType.NORMATIVA,
            source_filename="LISR.md",
            chunk_index=rank - 1,
            chunk_type=LegalChunkType.ARTICLE,
            legal_identifier=article,
            page_start=1,
            page_end=1,
            hierarchy=LegalHierarchy(article=article),
            source_sha256="a" * 64,
            fiscal_year=2026,
            version_label="2026-A",
        ),
    )


def _candidate(ref: str, legal_unit_id: int) -> NormativeCandidate:
    return NormativeCandidate(
        ref=ref,
        legal_unit_id=legal_unit_id,
        version_label="2026-A",
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 12, 31),
        fiscal_year=2026,
    )


def _rules(*, include_payment_trigger: bool = True) -> RuleSet:
    rules = [
        RuleDefinition(
            rule_id="ISR_PROFESSIONAL_CLASSIFY_001",
            version="1.0.0",
            description="Clasifica servicios profesionales independientes.",
            conditions=[
                RuleCondition(
                    fact="taxpayer_type",
                    operator=RuleOperator.EQ,
                    value="individual",
                ),
                RuleCondition(
                    fact="income_type",
                    operator=RuleOperator.EQ,
                    value="independent_professional_services",
                ),
            ],
            conclusion_code="isr_professional_income",
            conclusion="Ingreso profesional clasificado.",
            normative_refs=[ARTICLE_100_REF],
        )
    ]
    if include_payment_trigger:
        rules.append(
            RuleDefinition(
                rule_id="ISR_PROFESSIONAL_PAYMENT_002",
                version="1.0.0",
                description="Determina obligación de pago ISR.",
                conditions=[
                    RuleCondition(
                        fact="isr_professional_income",
                        operator=RuleOperator.EQ,
                        value=True,
                    )
                ],
                conclusion_code="isr_professional_payment_obligation",
                conclusion="Existe obligación de pago ISR.",
                normative_refs=[ARTICLE_100_REF],
            )
        )
    return RuleSet(schema_version="1.0", rules=rules)


def _tariff(*, validity: NormativeValidityStatus) -> ISRTariff:
    return ISRTariff(
        schema_version="1.0",
        version="TEST-2026",
        fiscal_year=2026,
        period=ISRPeriod.ANNUAL,
        normative_ref=ARTICLE_152_REF,
        source_reference="FIXTURE_ONLY",
        verified=True,
        legal_metadata=ISRTariffLegalMetadata(
            source_document_id="lisr",
            legal_basis_refs=[ARTICLE_152_REF],
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 12, 31),
            validity_status=validity,
        ),
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


def _input() -> ISRCalculationInput:
    return ISRCalculationInput(
        fiscal_year=2026,
        period=ISRPeriod.ANNUAL,
        gross_income=Decimal("20000"),
        exempt_income=Decimal("1000"),
        authorized_deductions=Decimal("2000"),
        credits=Decimal("100"),
        normative_ref=ARTICLE_152_REF,
    )


def _service(
    *,
    rule_set: RuleSet,
    tariff: ISRTariff,
) -> HybridOrchestrator:
    return HybridOrchestrator(
        query_analyzer=FakeAnalyzer(),
        retriever=FakeRetriever(),
        llm_service=LlamaRAGService(MockLLMProvider()),
        rule_set=rule_set,
        isr_tariff_registry=ISRTariffRegistry([tariff]),
    )


def _request() -> HybridOrchestrationRequest:
    return HybridOrchestrationRequest(
        query="Calcula ISR por servicios profesionales",
        query_date=date(2026, 8, 28),
        query_fiscal_year=2026,
        normative_candidates=[
            _candidate(ARTICLE_100_CHUNK, 100),
            _candidate(ARTICLE_152_CHUNK, 152),
        ],
        isr_input=_input(),
    )


def test_orchestrator_executes_isr_from_rbr_with_safe_registry() -> None:
    result = _service(
        rule_set=_rules(),
        tariff=_tariff(validity=NormativeValidityStatus.VERIFIED_IN_FORCE),
    ).run(_request())

    assert result.isr_result is not None
    assert result.isr_result.final_tax == Decimal("2300.00")
    assert any(
        item.conclusion_code == "isr_professional_payment_obligation"
        for item in result.rule_result.matched_rules
    )
    trace = next(item for item in result.traces if item.stage == OrchestrationStage.ISR)
    assert trace.status == StageStatus.COMPLETED
    assert "RBR" in trace.detail
    assert result.isr_trace is not None
    assert result.isr_trace.final_tax == Decimal("2300.00")
    assert result.isr_trace.legal.normative_ref == ARTICLE_152_REF
    assert result.isr_trace.authorization.rule_id == "ISR_PROFESSIONAL_PAYMENT_002"
    assert result.isr_trace_verification is not None
    assert result.isr_trace_verification.mathematically_consistent is True
    assert result.isr_trace_verification.legally_linked is True
    assert result.isr_trace_verification.rbr_authorized is True
    assert result.isr_trace_verification.verified is True


def test_orchestrator_does_not_calculate_without_rbr_payment_trigger() -> None:
    result = _service(
        rule_set=_rules(include_payment_trigger=False),
        tariff=_tariff(validity=NormativeValidityStatus.VERIFIED_IN_FORCE),
    ).run(_request())

    assert result.isr_result is None
    assert result.isr_trace is None
    assert result.isr_trace_verification is None
    trace = next(item for item in result.traces if item.stage == OrchestrationStage.ISR)
    assert trace.status == StageStatus.SKIPPED
    assert result.requires_human_review is True


def test_orchestrator_rejects_tariff_without_verified_fiscal_validity() -> None:
    result = _service(
        rule_set=_rules(),
        tariff=_tariff(validity=NormativeValidityStatus.UNKNOWN),
    ).run(_request())

    assert result.isr_result is None
    trace = next(item for item in result.traces if item.stage == OrchestrationStage.ISR)
    assert trace.status == StageStatus.DEGRADED
    assert result.requires_human_review is True
