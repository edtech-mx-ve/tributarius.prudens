from __future__ import annotations

from datetime import date

from app.domain.cbr import CaseStatus, CBRCase, CBRQuery
from app.domain.jurisprudence_decision_application import JurisprudenceDecisionEffect
from app.domain.llama_hybrid_context import LlamaHybridContextPhase
from app.domain.orchestration import HybridOrchestrationRequest
from app.domain.query import ExtractedFact, QueryAnalysis, QueryIntent
from app.services.hybrid_contract_baseline import audit_current_hybrid_contracts
from app.services.hybrid_jurisprudence_integration import (
    run_hybrid_with_session_jurisprudence,
)
from app.services.hybrid_orchestrator import HybridOrchestrator
from app.services.integral_legal_analyzer import build_integral_legal_analysis
from app.services.jurisprudence_metadata_extraction import (
    extract_jurisprudence_metadata_record,
)
from app.services.jurisprudence_normative_relations import (
    build_jurisprudence_normative_relation_record,
)
from app.services.jurisprudence_ratio import build_jurisprudence_ratio_record
from app.services.jurisprudence_temporal_control import (
    build_jurisprudence_temporal_record,
)
from app.services.legal_decision import build_legal_decision
from llm.models import LLMGenerationContext
from llm.providers.mock import MockLLMProvider
from llm.providers.mock_query import MockQueryAnalyzerProvider
from llm.query_analyzer import QueryAnalyzer
from llm.service import LlamaRAGService
from tests.test_block12_4_hypothesis_verification import _orchestrator, _request
from tests.test_block_e5_ratio_binding_adjustment import (
    DOC_ID as REFERENCE_DOC_ID,
)
from tests.test_block_e5_ratio_binding_adjustment import _document as reference_document
from tests.test_hybrid_orchestrator import (
    FakeAnalyzer,
    FakeRetriever,
    analysis,
    candidate,
    isr_input,
    retrieval,
    rules,
    tariff,
)


class CountingExplanationProvider(MockLLMProvider):
    def __init__(self) -> None:
        self.calls = 0

    def generate_json(
        self,
        context: LLMGenerationContext,
        *,
        response_schema: dict[str, object],
    ) -> str:
        self.calls += 1
        return super().generate_json(context, response_schema=response_schema)


class StaticOrchestrator:
    def __init__(self, result: object) -> None:
        self._result = result

    def run(self, request: HybridOrchestrationRequest):  # type: ignore[no-untyped-def]
        del request
        return self._result


def _rich_analysis() -> QueryAnalysis:
    analysis = QueryAnalyzer(MockQueryAnalyzerProvider()).analyze(
        "Quiero calcular ISR."
    )
    return analysis.model_copy(
        update={
            "facts": [
                ExtractedFact(name="fiscal_year", value="2026"),
                ExtractedFact(name="taxpayer_type", value="individual"),
            ],
            "missing_fields": [],
            "requires_clarification": False,
        }
    )


def _cbr_case() -> CBRCase:
    return CBRCase(
        case_id="CASE-F2-001",
        status=CaseStatus.ACTIVE,
        taxpayer_type="individual",
        activity="servicios profesionales",
        tax="ISR",
        problem_type="determinacion de obligaciones",
        procedural_stage="orientacion",
        fiscal_year=2026,
        resolution_summary="Caso F.2 sintético y validado.",
        normative_refs=["NORM_TEST_ISR_2026"],
        source_refs=["F2_TEST"],
    )


def _cbr_query() -> CBRQuery:
    return CBRQuery(
        taxpayer_type="individual",
        activity="servicios profesionales",
        tax="ISR",
        problem_type="determinacion de obligaciones",
        procedural_stage="orientacion",
        fiscal_year=2026,
    )


def _hybrid_result():  # type: ignore[no-untyped-def]
    return HybridOrchestrator(
        query_analyzer=FakeAnalyzer(_rich_analysis()),
        retriever=FakeRetriever(retrieval()),
        llm_service=LlamaRAGService(MockLLMProvider()),
        rule_set=rules(),
        isr_tariff=tariff(),
        cbr_cases=[_cbr_case()],
    ).run(
        HybridOrchestrationRequest(
            query="Calcula ISR 2026 para una persona física.",
            query_date=date(2026, 9, 3),
            query_fiscal_year=2026,
            normative_candidates=[candidate()],
            isr_input=isr_input(),
            cbr_query=_cbr_query(),
        )
    )


def _session_request(base_request: HybridOrchestrationRequest) -> HybridOrchestrationRequest:
    document = reference_document()
    metadata = extract_jurisprudence_metadata_record(document)
    relations = build_jurisprudence_normative_relation_record(
        document,
        metadata_record=metadata,
    )
    temporal = build_jurisprudence_temporal_record(metadata)
    ratio = build_jurisprudence_ratio_record(metadata)
    return base_request.model_copy(
        update={
            "query": "RESICO límite de ingresos artículo 113-E",
            "query_date": date(2026, 9, 3),
            "session_jurisprudence_documents": [document],
            "session_jurisprudence_metadata": {
                REFERENCE_DOC_ID: metadata.extracted
            },
            "session_jurisprudence_normative_relations": {
                REFERENCE_DOC_ID: relations
            },
            "session_jurisprudence_temporal_records": {
                REFERENCE_DOC_ID: temporal
            },
            "session_jurisprudence_ratio_records": {REFERENCE_DOC_ID: ratio},
        }
    )


def test_f2_builds_early_h1_context_from_query_analysis_and_d_route() -> None:
    result = _hybrid_result()
    context = result.llama_initial_context

    assert context is not None
    assert context.phase is LlamaHybridContextPhase.INITIAL_FISCAL_HYPOTHESIS
    assert context.primary_intent is QueryIntent.CALCULATE_ISR
    assert {item.name for item in context.facts} == {"fiscal_year", "taxpayer_type"}
    assert context.heuristic_route.primary_problem_id == "determinacion_contribucion"
    assert context.heuristic_route.primary_institution_id == "regimen_isr"
    assert context.heuristic_route.primary_manual_entry_ids
    assert context.heuristic_route.rbs_orientation_relation_ids
    assert context.heuristic_route.cbr_orientation_situation_ids
    assert context.heuristic_route.normative_focus_source_ids


def test_f2_h1_context_excludes_downstream_determinative_results() -> None:
    context = _hybrid_result().llama_initial_context

    assert context is not None
    assert context.retrieval_evidence_included is False
    assert context.normative_applicability_results_included is False
    assert context.rbs_determinative_result_included is False
    assert context.cbr_operational_result_included is False
    assert context.jurisprudence_ratio_included is False
    assert context.legal_decision_included is False
    assert context.requires_later_validation is True
    assert context.can_control_legal_decision is False


def test_f2_post_deterministic_context_exposes_rbs_cbr_and_heuristics() -> None:
    result = _hybrid_result()
    context = result.llama_hybrid_review_context

    assert context is not None
    assert context.phase is LlamaHybridContextPhase.POST_DETERMINISTIC_REVIEW
    assert "Perfil sujeto a revisión ISR." in context.rule_conclusions
    assert context.rbs_conclusion is not None
    assert context.cbr_case_refs == ["CASE-F2-001"]
    assert context.hybrid_relation is not None
    assert context.heuristic_signals
    assert context.source_results_already_computed is True
    assert context.can_change_deterministic_result is False
    assert context.can_control_legal_decision is False


def test_f2_context_preparation_does_not_add_extra_llm_generation_calls() -> None:
    provider = CountingExplanationProvider()
    service = HybridOrchestrator(
        query_analyzer=FakeAnalyzer(analysis()),
        retriever=FakeRetriever(retrieval()),
        llm_service=LlamaRAGService(provider),
        rule_set=rules(),
        isr_tariff=tariff(),
    )

    result = service.run(
        HybridOrchestrationRequest(
            query="Calcula ISR 2026 para una persona física.",
            query_date=date(2026, 9, 3),
            query_fiscal_year=2026,
            normative_candidates=[candidate()],
            isr_input=isr_input(),
        )
    )

    assert result.llama_initial_context is not None
    assert result.llama_hybrid_review_context is not None
    assert provider.calls == 1
    assert result.initial_legal_hypothesis is None
    assert result.llama_jurisprudence_ratio_contexts == []


def test_f2_session_jurisprudence_exposes_traceable_justification_context() -> None:
    base = _orchestrator(None).run(_request())
    query_analysis = QueryAnalysis(
        original_query="RESICO límite de ingresos artículo 113-E",
        normalized_query="RESICO límite ingresos artículo 113-E",
        primary_intent=QueryIntent.INTERPRET_PROVISION,
        facts=[
            ExtractedFact(name="fiscal_regime", value="RESICO"),
            ExtractedFact(name="issue", value="límite de ingresos"),
            ExtractedFact(name="matter", value="fiscal"),
        ],
    )
    base = base.model_copy(
        update={
            "analysis": query_analysis,
            "applicable_normative_refs": ["lisr:articulo_113_e"],
        }
    )
    request = _session_request(_request())

    result = run_hybrid_with_session_jurisprudence(
        StaticOrchestrator(base),
        request,
    )

    assert len(result.llama_jurisprudence_ratio_contexts) == 1
    context = result.llama_jurisprudence_ratio_contexts[0]
    assert context.phase is LlamaHybridContextPhase.JURISPRUDENTIAL_RATIO
    assert context.document_id == REFERENCE_DOC_ID
    assert "113-E" in context.justification_text
    assert context.justification_source_pages == [1]
    assert context.candidate_normative_refs == ["lisr:articulo_113_e"]
    assert context.binding_character_mandatory is True
    assert context.binding_from == date(2026, 4, 20)
    assert context.e5_authorized_for_evidence is True
    assert context.e6_application_result_included is False
    assert context.ratio_is_not_yet_authoritative is True
    assert context.can_control_legal_decision is False


def test_f2_jurisprudence_updates_review_context_without_becoming_legal_decision() -> None:
    base = _orchestrator(None).run(_request())
    query_analysis = QueryAnalysis(
        original_query="RESICO límite de ingresos artículo 113-E",
        normalized_query="RESICO límite ingresos artículo 113-E",
        primary_intent=QueryIntent.INTERPRET_PROVISION,
        facts=[
            ExtractedFact(name="fiscal_regime", value="RESICO"),
            ExtractedFact(name="issue", value="límite de ingresos"),
            ExtractedFact(name="matter", value="fiscal"),
        ],
    )
    base = base.model_copy(
        update={
            "analysis": query_analysis,
            "applicable_normative_refs": ["lisr:articulo_113_e"],
        }
    )

    result = run_hybrid_with_session_jurisprudence(
        StaticOrchestrator(base),
        _session_request(_request()),
    )
    review = result.llama_hybrid_review_context

    assert result.session_jurisprudence_result is not None
    assert result.session_jurisprudence_result.decision_application is not None
    assessment = result.session_jurisprudence_result.decision_application.assessments[0]
    assert assessment.decision_effect is JurisprudenceDecisionEffect.GOVERNING_INTERPRETATION
    assert review is not None
    assert review.jurisprudence_applicable_document_ids == [REFERENCE_DOC_ID]
    assert review.jurisprudence_binding_evidence_refs
    assert review.legal_decision_included is False
    assert review.may_explain_or_verify_only is True


def test_f2_new_contexts_do_not_change_analyzer_or_legal_decision() -> None:
    baseline = _orchestrator(None).run(_request())
    enriched = baseline.model_copy(
        update={
            "llama_initial_context": _hybrid_result().llama_initial_context,
            "llama_hybrid_review_context": _hybrid_result().llama_hybrid_review_context,
        }
    )

    baseline_analysis = build_integral_legal_analysis(baseline)
    enriched_analysis = build_integral_legal_analysis(enriched)
    baseline_decision = build_legal_decision(baseline_analysis)
    enriched_decision = build_legal_decision(enriched_analysis)

    assert enriched_analysis == baseline_analysis
    assert enriched_decision == baseline_decision


def test_f2_preserves_f1_contract_baseline_additively() -> None:
    audit = audit_current_hybrid_contracts()

    assert audit.all_contracts_preserved is True
    assert audit.real_llm_activation_performed is False
    assert audit.h1_h2_runtime_activation_performed is False
    assert audit.runtime_order_changed is False
    assert audit.legal_decision_changed is False


def test_f2_runtime_result_contract_exposes_three_separate_context_channels() -> None:
    result = _hybrid_result()

    assert result.llama_initial_context is not None
    assert result.llama_jurisprudence_ratio_contexts == []
    assert result.llama_hybrid_review_context is not None
    assert result.llama_initial_context.phase != result.llama_hybrid_review_context.phase
