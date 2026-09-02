from __future__ import annotations

import json
from datetime import date

from app.domain.legal_hypothesis_verification import (
    LegalHypothesisVerificationState,
)
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
    def __init__(self, hypothesis: str) -> None:
        self._hypothesis = hypothesis

    @property
    def provider_name(self) -> str:
        return "verification-static"

    @property
    def model_name(self) -> str:
        return "llama-verification-test"

    def generate_json(
        self,
        context: LLMGenerationContext,
        *,
        response_schema: dict[str, object],
    ) -> str:
        del response_schema
        return json.dumps(
            {
                "issue": "Posible obligación fiscal.",
                "hypothesis": self._hypothesis,
                "investigation_targets": [
                    "Verificar la regla y la normativa aplicable."
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


def _orchestrator(hypothesis: str | None) -> HybridOrchestrator:
    hypothesis_service = (
        LlamaLegalHypothesisService(HypothesisProvider(hypothesis))
        if hypothesis is not None
        else None
    )
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


def test_verification_runs_after_rules_and_before_explanation() -> None:
    result = _orchestrator(
        "Podría existir una obligación fiscal sujeta a validación."
    ).run(_request())

    verification = result.initial_legal_hypothesis_verification
    assert verification is not None
    assert verification.state == LegalHypothesisVerificationState.COMPARED
    assert verification.deterministic_conclusions == [
        "Perfil sujeto a revisión ISR."
    ]
    assert verification.controlling_source == "rbs"
    assert verification.semantic_equivalence_asserted is False
    assert verification.deterministic_result_preserved is True

    stages = [trace.stage for trace in result.traces]
    assert stages.index(OrchestrationStage.RULES) < stages.index(
        OrchestrationStage.LEGAL_HYPOTHESIS_VERIFICATION
    )
    assert stages.index(OrchestrationStage.LEGAL_HYPOTHESIS_VERIFICATION) < stages.index(
        OrchestrationStage.EXPLANATION
    )


def test_verification_does_not_treat_textual_difference_as_legal_contradiction() -> None:
    result = _orchestrator(
        "Hipótesis lingüísticamente distinta de la conclusión determinista."
    ).run(_request())

    verification = result.initial_legal_hypothesis_verification
    assert verification is not None
    assert verification.state == LegalHypothesisVerificationState.COMPARED
    assert verification.exact_text_match is False
    assert verification.semantic_equivalence_asserted is False
    assert result.rule_result.matched_rules[0].conclusion == (
        "Perfil sujeto a revisión ISR."
    )
    assert result.requires_human_review is False


def test_exact_text_match_is_experimental_only() -> None:
    result = _orchestrator("Perfil sujeto a revisión ISR.").run(_request())

    verification = result.initial_legal_hypothesis_verification
    assert verification is not None
    assert verification.exact_text_match is True
    assert verification.semantic_equivalence_asserted is False
    assert verification.controlling_source == "rbs"
    assert result.requires_human_review is False


def test_absent_hypothesis_is_not_applicable_and_preserves_compatibility() -> None:
    result = _orchestrator(None).run(_request())

    verification = result.initial_legal_hypothesis_verification
    assert verification is not None
    assert verification.state == LegalHypothesisVerificationState.NOT_APPLICABLE
    assert verification.deterministic_result_preserved is True

    trace = next(
        item
        for item in result.traces
        if item.stage == OrchestrationStage.LEGAL_HYPOTHESIS_VERIFICATION
    )
    assert trace.status.value == "skipped"


def test_hypothesis_verification_cannot_change_deterministic_result() -> None:
    baseline = _orchestrator(None).run(_request())
    experimental = _orchestrator(
        "Una hipótesis deliberadamente diferente para probar invariancia."
    ).run(_request())

    assert experimental.applicable_normative_refs == baseline.applicable_normative_refs
    assert experimental.rule_result == baseline.rule_result
    assert experimental.isr_result == baseline.isr_result
    assert experimental.hybrid_coordination == baseline.hybrid_coordination
    assert experimental.heuristic_evaluation == baseline.heuristic_evaluation
    assert experimental.requires_human_review == baseline.requires_human_review
