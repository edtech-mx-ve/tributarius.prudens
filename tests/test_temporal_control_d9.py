from __future__ import annotations

from datetime import date

from app.domain.chunks import ChunkMetadata, LegalChunkType, LegalHierarchy
from app.domain.documents import SourceType
from app.domain.normative import (
    NormativeApplicabilityRequest,
    NormativeDecision,
)
from app.domain.orchestration import (
    HybridOrchestrationRequest,
    NormativeCandidate,
    OrchestrationStage,
)
from app.domain.query import QueryAnalysis, TemporalYearResolution
from app.domain.rules import RuleCondition, RuleDefinition, RuleOperator, RuleSet
from app.services.hybrid_orchestrator import HybridOrchestrator
from app.services.normative_engine import evaluate_normative_applicability
from app.services.temporal_control import (
    execute_temporal_control,
    resolve_temporal_query_context,
)
from llm.providers.mock import MockLLMProvider
from llm.providers.runtime_query import RuntimeQueryAnalyzerProvider
from llm.query_analyzer import QueryAnalyzer
from llm.service import LlamaRAGService
from rag.retrieval.filters import RetrievalFilters
from rag.retrieval.models import RetrievalHit, RetrievalResult


def _analyze(query: str) -> QueryAnalysis:
    return QueryAnalyzer(RuntimeQueryAnalyzerProvider()).analyze(query)


def _hit(
    *,
    chunk_id: str,
    document_id: str = "lisr",
    legal_identifier: str = "Artículo 106",
    version_label: str = "2025",
    fiscal_year: int | None = None,
    effective_from: str | None = None,
    effective_to: str | None = None,
) -> RetrievalHit:
    return RetrievalHit(
        rank=1,
        score=0.95,
        chunk_id=chunk_id,
        text=f"{legal_identifier}. Contenido normativo de prueba.",
        metadata=ChunkMetadata(
            document_id=document_id,
            canonical_id=document_id,
            source_type=SourceType.NORMATIVA,
            source_filename=f"{document_id}.md",
            chunk_index=1,
            chunk_type=LegalChunkType.ARTICLE,
            legal_identifier=legal_identifier,
            source_unit_label=legal_identifier,
            hierarchy=LegalHierarchy(article=legal_identifier),
            source_sha256="c" * 64,
            version_label=version_label,
            fiscal_year=fiscal_year,
            effective_from=effective_from,
            effective_to=effective_to,
        ),
    )


def _retrieval(*hits: RetrievalHit) -> RetrievalResult:
    return RetrievalResult(
        query="consulta temporal",
        requested_top_k=5,
        candidate_count=len(hits),
        returned_count=len(hits),
        hits=[hit.model_copy(update={"rank": rank}) for rank, hit in enumerate(hits, 1)],
    )


def _candidate(
    ref: str,
    *,
    fiscal_year: int | None = None,
    effective_from: date | None = None,
    effective_to: date | None = None,
) -> NormativeCandidate:
    return NormativeCandidate(
        ref=ref,
        legal_unit_id=100,
        version_label="2025",
        fiscal_year=fiscal_year,
        effective_from=effective_from,
        effective_to=effective_to,
    )


def _result(
    candidate: NormativeCandidate,
    *,
    query_date: date,
    query_fiscal_year: int | None,
):
    return evaluate_normative_applicability(
        NormativeApplicabilityRequest(
            legal_unit_id=candidate.legal_unit_id,
            version_label=candidate.version_label,
            effective_from=candidate.effective_from,
            effective_to=candidate.effective_to,
            fiscal_year=candidate.fiscal_year,
            validity_status=candidate.validity_status,
            validity_scope=candidate.validity_scope,
            validity_basis=candidate.validity_basis,
            validity_verified_at=candidate.validity_verified_at,
            official_source=candidate.official_source,
            query_date=query_date,
            query_fiscal_year=query_fiscal_year,
        )
    )


class FilteringRetriever:
    def __init__(self, hits: list[RetrievalHit]) -> None:
        self.hits = hits

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> RetrievalResult:
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
        ][:top_k]
        return RetrievalResult(
            query=query,
            requested_top_k=top_k,
            candidate_count=len(eligible),
            returned_count=len(eligible),
            hits=[
                item.model_copy(update={"rank": rank})
                for rank, item in enumerate(eligible, start=1)
            ],
        )


def _rules() -> RuleSet:
    return RuleSet(
        schema_version="1.0",
        rules=[
            RuleDefinition(
                rule_id="D9_TEST_RULE",
                version="1.0",
                description="Regla sintética para verificar la frontera temporal D.9.",
                conditions=[
                    RuleCondition(
                        fact="taxpayer_type",
                        operator=RuleOperator.EQ,
                        value="corporation",
                    )
                ],
                conclusion_code="d9_test",
                conclusion="Sin efecto material fuera de la prueba D.9.",
            )
        ],
    )


def test_d9_plan_preserves_twelve_corpora_and_historical_rif_signal() -> None:
    analysis = _analyze("¿Cómo calculaba ISR una persona física en RIF durante 2020?")
    plan = analysis.temporal_control_plan

    assert plan is not None
    assert plan.explicit_query_years == [2020]
    assert plan.historical_context is True
    assert "liva" in plan.temporal_blocked_source_ids
    assert len(plan.normative_corpus_ids) == 12
    assert plan.fail_closed_unknown_validity is True
    assert plan.rule_promotion_requires_temporal_applicability is True
    assert plan.can_control_legal_decision is False


def test_d9_resolves_single_query_year_without_inventing_exact_date() -> None:
    analysis = _analyze(
        "Soy persona física y presto servicios profesionales; "
        "quiero calcular ISR del ejercicio 2025."
    )
    assert analysis.temporal_control_plan is not None

    resolution = resolve_temporal_query_context(analysis.temporal_control_plan, None)

    assert resolution.resolved_fiscal_year == 2025
    assert resolution.resolution is TemporalYearResolution.QUERY_EXPLICIT_YEAR
    assert resolution.conflict is False
    assert resolution.ambiguity is False
    assert resolution.blocks_promotion is False


def test_d9_conflicting_structured_year_blocks_promotion_fail_closed() -> None:
    analysis = _analyze(
        "Soy persona física y presto servicios profesionales; "
        "quiero calcular ISR del ejercicio 2025."
    )
    plan = analysis.temporal_control_plan
    assert plan is not None
    resolution = resolve_temporal_query_context(plan, 2026)
    candidate = _candidate(
        "lisr-106-conflict",
        effective_from=date(2025, 1, 1),
        effective_to=date(2026, 12, 31),
    )
    result = _result(candidate, query_date=date(2026, 9, 3), query_fiscal_year=2026)

    execution = execute_temporal_control(
        plan=plan,
        query_date=date(2026, 9, 3),
        resolution=resolution,
        retrieval=_retrieval(_hit(chunk_id=candidate.ref)),
        candidates=[candidate],
        normative_results=[result],
        evidence_refs=[candidate.ref],
        applicable_refs=[candidate.ref],
        temporal_guard=None,
    )

    assert resolution.resolution is TemporalYearResolution.CONFLICT
    assert execution.query_temporal_conflict is True
    assert execution.applicable_count == 1
    assert execution.promoted_count == 0
    assert execution.promoted_normative_refs == []
    assert execution.requires_human_review is True


def test_d9_multiple_query_years_without_structured_year_are_ambiguous() -> None:
    analysis = _analyze(
        "Soy persona física y presto servicios profesionales; "
        "quiero calcular ISR del ejercicio 2025."
    )
    plan = analysis.temporal_control_plan
    assert plan is not None
    plan = plan.model_copy(update={"explicit_query_years": [2024, 2025]})

    resolution = resolve_temporal_query_context(plan, None)

    assert resolution.resolution is TemporalYearResolution.AMBIGUOUS_QUERY_YEARS
    assert resolution.resolved_fiscal_year is None
    assert resolution.ambiguity is True
    assert resolution.blocks_promotion is True


def test_d9_unknown_validity_is_preserved_as_evidence_but_never_promoted() -> None:
    analysis = _analyze("Quiero conocer mis obligaciones fiscales en 2025.")
    plan = analysis.temporal_control_plan
    assert plan is not None
    resolution = resolve_temporal_query_context(plan, 2025)
    candidate = _candidate("cff-unknown", fiscal_year=2025)
    result = _result(candidate, query_date=date(2025, 6, 1), query_fiscal_year=2025)

    assert result.decision is NormativeDecision.UNKNOWN_VALIDITY
    execution = execute_temporal_control(
        plan=plan,
        query_date=date(2025, 6, 1),
        resolution=resolution,
        retrieval=_retrieval(
            _hit(chunk_id=candidate.ref, document_id="cff", fiscal_year=2025)
        ),
        candidates=[candidate],
        normative_results=[result],
        evidence_refs=[candidate.ref],
        applicable_refs=[],
        temporal_guard=None,
    )

    assert execution.evidence_refs == [candidate.ref]
    assert execution.unknown_validity_refs == [candidate.ref]
    assert execution.promoted_normative_refs == []
    assert execution.all_temporal_questions_resolved is False
    assert execution.requires_human_review is True


def test_d9_classifies_expired_future_and_fiscal_year_mismatch_without_erasing_evidence() -> None:
    analysis = _analyze("Quiero revisar obligaciones fiscales del ejercicio 2025.")
    plan = analysis.temporal_control_plan
    assert plan is not None
    resolution = resolve_temporal_query_context(plan, 2025)
    expired = _candidate(
        "lisr-expired",
        effective_from=date(2024, 1, 1),
        effective_to=date(2024, 12, 31),
    )
    future = _candidate("lisr-future", effective_from=date(2026, 1, 1))
    mismatch = _candidate(
        "rmf-mismatch",
        fiscal_year=2026,
        effective_from=date(2025, 1, 1),
    )
    candidates = [expired, future, mismatch]
    results = [
        _result(item, query_date=date(2025, 6, 1), query_fiscal_year=2025)
        for item in candidates
    ]

    execution = execute_temporal_control(
        plan=plan,
        query_date=date(2025, 6, 1),
        resolution=resolution,
        retrieval=_retrieval(
            _hit(chunk_id=expired.ref),
            _hit(chunk_id=future.ref),
            _hit(chunk_id=mismatch.ref, document_id="rmf_2026"),
        ),
        candidates=candidates,
        normative_results=results,
        evidence_refs=[item.ref for item in candidates],
        applicable_refs=[],
        temporal_guard=None,
    )

    assert execution.expired_refs == [expired.ref]
    assert execution.not_yet_effective_refs == [future.ref]
    assert execution.fiscal_year_mismatch_refs == [mismatch.ref]
    assert set(execution.evidence_refs) == {item.ref for item in candidates}
    assert execution.promoted_count == 0


def test_d9_orchestrator_promotes_only_temporally_applicable_norms() -> None:
    query = (
        "Soy persona física y presto servicios profesionales; "
        "quiero calcular ISR del ejercicio 2025."
    )
    hit = _hit(
        chunk_id="lisr-106-runtime-d9",
        document_id="lisr",
        legal_identifier="Artículo 106",
        fiscal_year=2025,
        effective_from="2025-01-01",
        effective_to="2025-12-31",
    )
    service = HybridOrchestrator(
        query_analyzer=QueryAnalyzer(RuntimeQueryAnalyzerProvider()),
        retriever=FilteringRetriever([hit]),
        llm_service=LlamaRAGService(MockLLMProvider()),
        rule_set=_rules(),
    )

    result = service.run(
        HybridOrchestrationRequest(
            query=query,
            query_date=date(2025, 6, 1),
            query_fiscal_year=None,
            top_k=5,
        )
    )

    execution = result.temporal_control_execution
    assert execution is not None
    assert execution.resolved_query_fiscal_year == 2025
    assert execution.year_resolution is TemporalYearResolution.QUERY_EXPLICIT_YEAR
    assert execution.promoted_normative_refs == ["lisr-106-runtime-d9"]
    assert result.applicable_normative_refs == execution.promoted_normative_refs
    assert execution.temporal_validation_completed is True
    assert execution.can_control_legal_decision is False
    temporal_trace = next(
        item for item in result.traces if item.stage is OrchestrationStage.TEMPORAL
    )
    assert "Control temporal D.9" in temporal_trace.detail
