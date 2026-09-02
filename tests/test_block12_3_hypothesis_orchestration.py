from __future__ import annotations

import json
from datetime import date

from app.domain.orchestration import HybridOrchestrationRequest, OrchestrationStage
from app.services.hybrid_orchestrator import HybridOrchestrator
from app.services.legal_hypothesis_generation import LlamaLegalHypothesisService
from llm.models import LLMGenerationContext
from llm.providers.mock import MockLLMProvider
from llm.service import LlamaRAGService
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


class HypothesisProvider:
    @property
    def provider_name(self) -> str:
        return "hypothesis-static"

    @property
    def model_name(self) -> str:
        return "llama-hypothesis-test"

    def generate_json(
        self,
        context: LLMGenerationContext,
        *,
        response_schema: dict[str, object],
    ) -> str:
        del response_schema
        return json.dumps(
            {
                "issue": "Posible obligación fiscal aplicable.",
                "hypothesis": (
                    "Podría existir una obligación que debe validarse contra "
                    "la normativa y las reglas deterministas."
                ),
                "investigation_targets": [
                    "Verificar aplicabilidad normativa y hechos relevantes."
                ],
                "evidence_ids": [context.evidence[0].chunk_id],
                "uncertainties": [],
                "status": "proposed",
                "requires_validation": True,
                "changes_deterministic_result": False,
                "asserts_external_legal_authority": False,
            },
            ensure_ascii=False,
        )


class ExplodingHypothesisProvider:
    @property
    def provider_name(self) -> str:
        return "hypothesis-exploding"

    @property
    def model_name(self) -> str:
        return "llama-hypothesis-exploding"

    def generate_json(
        self,
        context: LLMGenerationContext,
        *,
        response_schema: dict[str, object],
    ) -> str:
        del context, response_schema
        raise RuntimeError("hypothesis provider unavailable")


def _orchestrator(
    *,
    hypothesis_service: LlamaLegalHypothesisService | None,
) -> HybridOrchestrator:
    return HybridOrchestrator(
        query_analyzer=FakeAnalyzer(analysis()),
        retriever=FakeRetriever(retrieval()),
        llm_service=LlamaRAGService(MockLLMProvider()),
        rule_set=rules(),
        legal_hypothesis_service=hypothesis_service,
        isr_tariff=tariff(),
    )


def _request() -> HybridOrchestrationRequest:
    return HybridOrchestrationRequest(
        query="Calcula ISR",
        query_date=date(2026, 8, 28),
        query_fiscal_year=2026,
        normative_candidates=[candidate()],
        isr_input=isr_input(),
    )


def test_hypothesis_runs_after_retrieval_and_before_deterministic_legal_stages() -> None:
    result = _orchestrator(
        hypothesis_service=LlamaLegalHypothesisService(HypothesisProvider())
    ).run(_request())

    assert result.initial_legal_hypothesis is not None
    assert result.initial_legal_hypothesis.generation_performed is True
    assert result.initial_legal_hypothesis.hypothesis is not None
    assert result.initial_legal_hypothesis.hypothesis.requires_validation is True

    stages = [trace.stage for trace in result.traces]
    assert stages.index(OrchestrationStage.RETRIEVAL) < stages.index(
        OrchestrationStage.LEGAL_HYPOTHESIS
    )
    assert stages.index(OrchestrationStage.LEGAL_HYPOTHESIS) < stages.index(
        OrchestrationStage.NORMATIVE
    )
    assert stages.index(OrchestrationStage.LEGAL_HYPOTHESIS) < stages.index(
        OrchestrationStage.RULES
    )


def test_hypothesis_does_not_change_deterministic_result() -> None:
    baseline = _orchestrator(hypothesis_service=None).run(_request())
    experimental = _orchestrator(
        hypothesis_service=LlamaLegalHypothesisService(HypothesisProvider())
    ).run(_request())

    assert experimental.applicable_normative_refs == baseline.applicable_normative_refs
    assert experimental.rule_result == baseline.rule_result
    assert experimental.isr_result == baseline.isr_result
    assert experimental.hybrid_coordination == baseline.hybrid_coordination
    assert experimental.heuristic_evaluation == baseline.heuristic_evaluation
    assert experimental.requires_human_review == baseline.requires_human_review


def test_hypothesis_provider_failure_does_not_block_or_escalate_legal_result() -> None:
    baseline = _orchestrator(hypothesis_service=None).run(_request())
    failed = _orchestrator(
        hypothesis_service=LlamaLegalHypothesisService(
            ExplodingHypothesisProvider()
        )
    ).run(_request())

    hypothesis_trace = next(
        trace
        for trace in failed.traces
        if trace.stage == OrchestrationStage.LEGAL_HYPOTHESIS
    )

    assert failed.initial_legal_hypothesis is None
    assert hypothesis_trace.status.value == "degraded"
    assert failed.applicable_normative_refs == baseline.applicable_normative_refs
    assert failed.rule_result == baseline.rule_result
    assert failed.isr_result == baseline.isr_result
    assert failed.requires_human_review == baseline.requires_human_review


def test_existing_orchestrator_without_hypothesis_service_remains_compatible() -> None:
    result = _orchestrator(hypothesis_service=None).run(_request())

    assert result.initial_legal_hypothesis is None
    hypothesis_trace = next(
        trace
        for trace in result.traces
        if trace.stage == OrchestrationStage.LEGAL_HYPOTHESIS
    )
    assert hypothesis_trace.status.value == "skipped"
