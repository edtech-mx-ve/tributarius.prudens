from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.domain.cbr import CaseStatus, CBRCase, CBRQuery
from app.domain.hybrid_legal_decision import HybridLegalDecisionStatus
from app.domain.hybrid_legal_verification import HybridLegalVerificationState
from app.domain.hybrid_llama_runtime import HybridLlamaRuntimeStatus
from app.domain.orchestration import HybridOrchestrationRequest
from app.services.hybrid_llama_runtime import (
    HybridLlamaRuntime,
    build_hybrid_llama_service_bundle,
)
from app.services.hybrid_orchestrator import HybridOrchestrator
from llm.errors import LLMGenerationError
from llm.models import LLMGenerationContext
from llm.providers.llama_cpp import LlamaCppProvider
from llm.service import LlamaRAGService
from tests.test_block_f2_llama_hybrid_context import (
    _cbr_case,
    _session_request,
)
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


class ScriptedStructuredProvider:
    """Doble F.10: mismo contrato estructurado que LlamaCppProvider, sólo para tests."""

    def __init__(self, events: list[str], *, fail_task: str | None = None) -> None:
        self.events = events
        self.fail_task = fail_task

    @property
    def provider_name(self) -> str:
        return "f10-scripted-test-double"

    @property
    def model_name(self) -> str:
        return "scripted-structured-test"

    def generate_json(
        self,
        context: LLMGenerationContext,
        *,
        response_schema: dict[str, object],
    ) -> str:
        del response_schema
        self.events.append("rag_explanation")
        deterministic = context.deterministic_evidence
        return json.dumps(
            {
                "summary": "Explicación estructurada de prueba.",
                "analysis": "La explicación respeta la evidencia determinista recibida.",
                "evidence_ids": [item.chunk_id for item in context.evidence[:2]],
                "normative_refs": (
                    list(deterministic.applicable_normative_refs)
                    if deterministic is not None
                    else []
                ),
                "rule_refs": (
                    list(deterministic.rule_conclusions)
                    if deterministic is not None
                    else []
                ),
                "calculation_refs": (
                    list(deterministic.calculations)
                    if deterministic is not None
                    else []
                ),
                "cbr_refs": (
                    list(deterministic.similar_cases)
                    if deterministic is not None
                    else []
                ),
                "jurisprudence_refs": (
                    list(deterministic.jurisprudential_criteria)
                    if deterministic is not None
                    else []
                ),
                "uncertainties": [],
                "requires_human_review": bool(
                    deterministic is not None and deterministic.requires_human_review
                ),
                "changes_deterministic_result": False,
                "asserts_external_legal_authority": False,
            },
            ensure_ascii=False,
        )

    def generate_messages_json(
        self,
        messages: list[dict[str, str]],
        *,
        response_schema: dict[str, object],
    ) -> str:
        del response_schema
        payload = json.loads(messages[-1]["content"])
        task = str(payload["task"])
        self.events.append(task)
        if task == self.fail_task:
            raise LLMGenerationError(f"fallo sintético {task}")
        if task == "formular_h1_fiscal_inicial_controlada":
            catalog = payload["selection_catalog"]
            facts = list(catalog.get("facts", []))
            institutions = list(catalog.get("institutions", []))
            normative_refs = list(catalog.get("normative_refs", []))
            return json.dumps(
                {
                    "legal_problem": "Determinar la consecuencia fiscal controlada.",
                    "proposition": "Perfil sujeto a revisión ISR.",
                    "facts_used": [
                        {
                            "name": item["name"],
                            "value": item["value"],
                            "origin": item["origin"],
                        }
                        for item in facts[:2]
                    ],
                    "institutions": (
                        [str(institutions[0]["value"])] if institutions else []
                    ),
                    "candidate_normative_refs": (
                        [str(normative_refs[0]["value"])] if normative_refs else []
                    ),
                    "candidate_normative_questions": [
                        "¿Qué norma aplicable sustenta la consecuencia?"
                    ],
                    "assumptions": [],
                    "uncertainties": [],
                    "confidence": 0.61,
                    "requires_validation": True,
                    "changes_deterministic_result": False,
                    "can_control_legal_decision": False,
                    "asserts_external_legal_authority": False,
                },
                ensure_ascii=False,
            )
        if task == "formular_h2_ratio_decidendi_controlada":
            catalog = payload["selection_catalog"]
            support_spans = list(catalog.get("support_spans", []))
            normative_refs = list(catalog.get("normative_refs", []))
            return json.dumps(
                {
                    "legal_question": "¿Cuál es la premisa indispensable del criterio?",
                    "normative_ref_indices": [0] if normative_refs else [],
                    "support_span_indices": [0] if support_spans else [],
                    "proposed_ratio": (
                        "La ratio propuesta queda limitada a la premisa indispensable "
                        "anclada en la Justificación."
                    ),
                    "obiter_span_indices": [],
                    "confidence_band": "high",
                },
                ensure_ascii=False,
            )
        if task == "verificar_argumento_hibrido_sin_redecidir":
            packet = payload["packet"]
            h1_present = packet.get("h1") is not None
            h2_items = {
                str(index): {
                    "source_fidelity": "consistent",
                    "consistency_with_coordinated_argument": "consistent",
                }
                for index, _item in enumerate(packet.get("h2", []))
            }
            binding = bool(
                packet.get("binding_jurisprudence", {}).get(
                    "applicable_document_ids", []
                )
            )
            return json.dumps(
                {
                    "h1_consistency": "consistent" if h1_present else "not_applicable",
                    "rbs_representation": "consistent",
                    "cbr_role": "consistent",
                    "h2_assessments": h2_items,
                    "binding_jurisprudence_consistency": (
                        "consistent" if binding else "not_applicable"
                    ),
                    "contradiction_codes": [],
                    "hallucination_signals": [],
                    "requires_human_review": False,
                },
                ensure_ascii=False,
            )
        raise AssertionError(f"task F.10 inesperada: {task}")


class EventRetriever(FakeRetriever):
    def __init__(self, events: list[str]) -> None:
        super().__init__(retrieval())
        self.events = events

    def search(self, query: str, *, top_k: int = 5, filters=None):  # type: ignore[no-untyped-def]
        self.events.append("retrieval")
        return super().search(query, top_k=top_k, filters=filters)


def _matching_case() -> CBRCase:
    return CBRCase(
        case_id="CASE-F10-001",
        status=CaseStatus.ACTIVE,
        taxpayer_type="individual",
        activity="servicios profesionales",
        tax="ISR",
        problem_type="determinacion de obligaciones",
        procedural_stage="orientacion",
        fiscal_year=2026,
        resolution_summary="Perfil sujeto a revisión ISR.",
        normative_refs=["NORM_TEST_ISR_2026"],
        source_refs=["F10_TEST"],
    )


def _request() -> HybridOrchestrationRequest:
    return HybridOrchestrationRequest(
        query="Calcula ISR 2026 para una persona física.",
        query_date=date(2026, 9, 3),
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


def _runtime(
    provider: ScriptedStructuredProvider,
    *,
    retriever: FakeRetriever | None = None,
    rich: bool = False,
) -> HybridLlamaRuntime:
    services = build_hybrid_llama_service_bundle(provider)
    orchestrator = HybridOrchestrator(
        query_analyzer=FakeAnalyzer(analysis()),
        retriever=retriever or FakeRetriever(retrieval()),
        llm_service=LlamaRAGService(provider),
        rule_set=rules(),
        isr_tariff=tariff(),
        cbr_cases=[_matching_case() if not rich else _cbr_case()],
        hybrid_h1_service=services.h1,
    )
    return HybridLlamaRuntime(
        orchestrator=orchestrator,
        services=services,
        provider_is_test_double=True,
    )


def test_f10_generates_h1_before_retrieval_and_then_contrasts_it() -> None:
    events: list[str] = []
    provider = ScriptedStructuredProvider(events)
    runtime = _runtime(provider, retriever=EventRetriever(events))

    result = runtime.run(_request())

    assert events.index("formular_h1_fiscal_inicial_controlada") < events.index("retrieval")
    assert result.orchestration.llama_fiscal_hypothesis_h1 is not None
    assert result.orchestration.rbs_h1_contrast is not None
    assert result.orchestration.cbr_h1_contrast is not None
    assert result.orchestration.rbs_h1_contrast.hypothesis_changes_rbs_result is False
    assert result.orchestration.cbr_h1_contrast.hypothesis_changes_cbr_result is False


def test_f10_executes_f2_to_f9_with_structured_provider_contract() -> None:
    provider = ScriptedStructuredProvider([])
    result = _runtime(provider).run(_request())

    assert result.status is HybridLlamaRuntimeStatus.COMPLETED
    assert result.provider_is_test_double is True
    assert result.production_requires_real_llama is True
    assert result.mock_allowed_for_tests_only is True
    assert result.h1_generation_attempted is True
    assert result.semantic_verification_attempted is True
    assert result.orchestration.hybrid_legal_coordination is not None
    assert result.orchestration.hybrid_legal_verification is not None
    assert result.orchestration.hybrid_legal_verification.semantic_verification_performed
    assert result.analysis.hybrid_verification_consumed is True
    assert result.decision.hybrid_projection.single_determination_preserved is True
    assert result.decision.legal_authority_reassigned_by_llm is False


def test_f10_llama_cpp_is_the_real_provider_contract_for_f11() -> None:
    assert callable(LlamaCppProvider.generate_json)
    assert callable(LlamaCppProvider.generate_messages_json)
    assert isinstance(LlamaCppProvider.provider_name, property)
    assert isinstance(LlamaCppProvider.model_name, property)
    assert Path("modelo.gguf").suffix == ".gguf"


def test_f10_generates_h2_only_when_session_jurisprudence_provides_context() -> None:
    provider = ScriptedStructuredProvider([])
    runtime = _runtime(provider, rich=True)
    request = _session_request(_request())

    result = runtime.run(request)

    assert result.h2_generation_attempted is True
    assert result.orchestration.llama_jurisprudence_ratio_contexts
    assert result.orchestration.llama_jurisprudential_ratio_h2
    ratio = result.orchestration.llama_jurisprudential_ratio_h2[0].ratio
    assert ratio is not None
    assert ratio.ratio_source_section.value == "justification"
    assert result.orchestration.hybrid_legal_verification is not None
    assert result.orchestration.hybrid_legal_verification.semantic_verification_performed


def test_f10_semantic_provider_failure_fails_closed_without_new_authority() -> None:
    provider = ScriptedStructuredProvider(
        [],
        fail_task="verificar_argumento_hibrido_sin_redecidir",
    )
    result = _runtime(provider).run(_request())

    assert result.status is HybridLlamaRuntimeStatus.DEGRADED
    assert result.llm_failure_codes == ["semantic_verification_failed"]
    assert result.orchestration.hybrid_legal_verification is not None
    assert (
        result.orchestration.hybrid_legal_verification.state
        is HybridLegalVerificationState.HUMAN_REVIEW
    )
    assert result.decision.status is HybridLegalDecisionStatus.HUMAN_REVIEW_REQUIRED
    assert result.decision.conclusion is None
    assert result.decision.legal_authority_reassigned_by_llm is False
