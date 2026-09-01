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
    HybridOrchestrationResult,
    NormativeCandidate,
    OrchestrationStage,
    StageStatus,
    StageTrace,
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


class Block6Analyzer:
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


class Block6Retriever:
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
        score=Decimal("0.99"),
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
    rule_set: RuleSet | None = None,
    validity: NormativeValidityStatus = NormativeValidityStatus.VERIFIED_IN_FORCE,
) -> HybridOrchestrator:
    return HybridOrchestrator(
        query_analyzer=Block6Analyzer(),
        retriever=Block6Retriever(),
        llm_service=LlamaRAGService(MockLLMProvider()),
        rule_set=rule_set or _rules(),
        isr_tariff_registry=ISRTariffRegistry([_tariff(validity=validity)]),
    )


def _request(
    *,
    include_article_152_candidate: bool = True,
) -> HybridOrchestrationRequest:
    candidates = [_candidate(ARTICLE_100_CHUNK, 100)]
    if include_article_152_candidate:
        candidates.append(_candidate(ARTICLE_152_CHUNK, 152))
    return HybridOrchestrationRequest(
        query="Calcula ISR por servicios profesionales",
        query_date=date(2026, 8, 28),
        query_fiscal_year=2026,
        normative_candidates=candidates,
        isr_input=_input(),
    )


def _isr_stage(result: HybridOrchestrationResult) -> StageTrace:
    return next(
        item for item in result.traces if item.stage == OrchestrationStage.ISR
    )


def test_block6_positive_path_is_integrally_reconstructable() -> None:
    result = _service().run(_request())

    assert result.isr_result is not None
    assert result.isr_result.final_tax == Decimal("2300.00")
    assert result.isr_trace is not None
    assert result.isr_trace.input.gross_income == Decimal("20000")
    assert result.isr_trace.input.exempt_income == Decimal("1000")
    assert result.isr_trace.input.authorized_deductions == Decimal("2000")
    assert result.isr_trace.input.credits == Decimal("100")
    assert result.isr_trace.legal.normative_ref == ARTICLE_152_REF
    assert result.isr_trace.legal.tariff_version == "TEST-2026"
    assert result.isr_trace.authorization.rule_id == "ISR_PROFESSIONAL_PAYMENT_002"
    assert [step.code for step in result.isr_trace.steps] == [
        "taxable_base",
        "excess_over_lower_limit",
        "marginal_tax",
        "tax_before_credits",
        "final_tax",
    ]
    assert result.isr_trace_verification is not None
    assert result.isr_trace_verification.mathematically_consistent is True
    assert result.isr_trace_verification.legally_linked is True
    assert result.isr_trace_verification.rbr_authorized is True
    assert result.isr_trace_verification.verified is True
    assert _isr_stage(result).status == StageStatus.COMPLETED


def test_block6_rbr_is_mandatory_for_safe_calculation() -> None:
    result = _service(rule_set=_rules(include_payment_trigger=False)).run(_request())

    assert result.isr_result is None
    assert result.isr_trace is None
    assert result.isr_trace_verification is None
    assert _isr_stage(result).status == StageStatus.SKIPPED
    assert result.requires_human_review is True


def test_block6_rejects_unverified_tariff_without_fallback() -> None:
    result = _service(validity=NormativeValidityStatus.UNKNOWN).run(_request())

    assert result.isr_result is None
    assert result.isr_trace is None
    assert result.isr_trace_verification is None
    assert _isr_stage(result).status == StageStatus.DEGRADED
    assert result.requires_human_review is True


def test_block6_requires_applicable_tariff_normative_basis() -> None:
    result = _service().run(_request(include_article_152_candidate=False))

    assert result.isr_result is None
    assert result.isr_trace is None
    assert result.isr_trace_verification is None
    assert _isr_stage(result).status in {StageStatus.SKIPPED, StageStatus.DEGRADED}
    assert result.requires_human_review is True


def test_block6_is_reproducible_for_same_inputs_rules_and_tariff() -> None:
    first = _service().run(_request())
    second = _service().run(_request())

    assert first.isr_result is not None
    assert second.isr_result is not None
    assert first.isr_result == second.isr_result
    assert first.isr_trace == second.isr_trace
    assert first.isr_trace_verification == second.isr_trace_verification


def test_block6_rule_and_tariff_foundations_remain_separate_in_trace() -> None:
    result = _service().run(_request())

    assert result.isr_trace is not None
    assert ARTICLE_100_REF in result.isr_trace.authorization.normative_refs
    assert result.isr_trace.legal.normative_ref == ARTICLE_152_REF
    assert ARTICLE_152_REF in result.isr_trace.legal.legal_basis_refs
    assert (
        result.isr_trace.authorization.normative_refs
        != result.isr_trace.legal.legal_basis_refs
    )
