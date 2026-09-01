from datetime import date

from app.domain.orchestration import HybridOrchestrationRequest, OrchestrationStage
from app.domain.rules import RuleCondition, RuleDefinition, RuleOperator, RuleSet
from app.services.hybrid_orchestrator import HybridOrchestrator
from llm.providers.mock import MockLLMProvider
from llm.service import LlamaRAGService
from tests.test_hybrid_orchestrator import (
    FakeAnalyzer,
    FakeRetriever,
    analysis,
    candidate,
    retrieval,
)


def _chained_rules() -> RuleSet:
    return RuleSet(
        schema_version="1.0",
        rules=[
            RuleDefinition(
                rule_id="PROFILE_CHAIN_001",
                version="1.0",
                description="Deriva un perfil fiscal desde un hecho explícito.",
                priority=300,
                conditions=[
                    RuleCondition(
                        fact="taxpayer_type",
                        operator=RuleOperator.EQ,
                        value="individual",
                    )
                ],
                conclusion_code="individual_profile",
                conclusion="Perfil fiscal individual identificado.",
                normative_refs=["NORM_TEST_ISR_2026"],
            ),
            RuleDefinition(
                rule_id="ISR_CHAIN_002",
                version="1.0",
                description="Usa una inferencia previa para continuar el razonamiento.",
                priority=200,
                conditions=[
                    RuleCondition(
                        fact="individual_profile",
                        operator=RuleOperator.EQ,
                        value=True,
                    )
                ],
                conclusion_code="review_isr_obligations",
                conclusion="Corresponde revisar obligaciones ISR.",
                normative_refs=["NORM_TEST_ISR_2026"],
            ),
        ],
    )


def test_orchestrator_executes_forward_chaining_rbr() -> None:
    fake_retriever = FakeRetriever(retrieval())
    service = HybridOrchestrator(
        query_analyzer=FakeAnalyzer(analysis()),
        retriever=fake_retriever,
        llm_service=LlamaRAGService(MockLLMProvider()),
        rule_set=_chained_rules(),
    )

    result = service.run(
        HybridOrchestrationRequest(
            query="Calcula ISR",
            query_date=date(2026, 8, 28),
            query_fiscal_year=2026,
            normative_candidates=[candidate()],
        )
    )

    assert result.applicable_normative_refs == ["NORM_TEST_ISR_2026"]
    assert [item.rule_id for item in result.rule_result.matched_rules] == [
        "PROFILE_CHAIN_001",
        "ISR_CHAIN_002",
    ]
    rules_trace = next(
        item for item in result.traces if item.stage == OrchestrationStage.RULES
    )
    assert rules_trace.detail == "Reglas activadas: 2."


def test_orchestrator_keeps_normative_gate_during_chaining() -> None:
    fake_retriever = FakeRetriever(retrieval())
    service = HybridOrchestrator(
        query_analyzer=FakeAnalyzer(analysis()),
        retriever=fake_retriever,
        llm_service=LlamaRAGService(MockLLMProvider()),
        rule_set=_chained_rules(),
    )

    result = service.run(
        HybridOrchestrationRequest(
            query="Calcula ISR",
            query_date=date(2027, 1, 1),
            query_fiscal_year=2027,
            normative_candidates=[candidate()],
        )
    )

    assert result.applicable_normative_refs == []
    assert result.rule_result.matched_rules == []
