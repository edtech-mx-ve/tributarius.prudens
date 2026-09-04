from __future__ import annotations

import inspect

from app.domain.hybrid_contract_baseline import HybridContractKind
from app.domain.legal_hypothesis import ControlledLegalHypothesis
from app.domain.orchestration import HybridOrchestrationResult
from app.services.hybrid_contract_baseline import (
    audit_current_hybrid_contracts,
    load_hybrid_contract_baseline,
)
from app.services.hybrid_orchestrator import HybridOrchestrator
from llm.providers.mock import MockLLMProvider
from llm.service import LlamaRAGService


def test_f1_baseline_is_bound_to_block_e_production_commit() -> None:
    baseline = load_hybrid_contract_baseline()

    assert baseline.schema_version == "1.0"
    assert baseline.baseline_commit == "06f06aa"
    assert baseline.runtime.explanation_provider == "MockLLMProvider"
    assert baseline.runtime.explanation_runtime == "deterministic_mock_until_sprint20"
    assert baseline.runtime.additive_evolution_only is True


def test_f1_all_current_public_contracts_are_preserved() -> None:
    audit = audit_current_hybrid_contracts()

    assert audit.all_contracts_preserved is True
    assert all(item.preserved for item in audit.checks)
    assert all(item.preserved for item in audit.runtime_checks)
    assert audit.real_llm_activation_performed is False
    assert audit.h1_h2_runtime_activation_performed is False
    assert audit.runtime_order_changed is False
    assert audit.legal_decision_changed is False


def test_f1_baseline_covers_all_hybrid_layers() -> None:
    baseline = load_hybrid_contract_baseline()
    components = {item.component for item in baseline.contracts}

    assert {
        "LLMProvider",
        "LlamaRAGService",
        "LlamaLegalHypothesisService",
        "QueryAnalysis",
        "ControlledLegalHypothesis",
        "RuleEvaluationResult",
        "CBRRetrievalResult",
        "HybridCoordinationResult",
        "HybridOrchestrationRequest",
        "HybridOrchestrationResult",
        "SessionJurisprudenceHybridResult",
        "JurisprudenceDecisionApplicationRecord",
        "IntegralLegalAnalysis",
        "LegalDecision",
    }.issubset(components)


def test_f1_contract_evolution_is_additive_not_exact_shape_locking() -> None:
    baseline = load_hybrid_contract_baseline()

    assert all(
        item.kind
        in {
            HybridContractKind.PYDANTIC_MODEL,
            HybridContractKind.ENUM,
            HybridContractKind.CALLABLE,
        }
        for item in baseline.contracts
    )
    assert baseline.runtime.additive_evolution_only is True


def test_f1_llama_explanation_keeps_jurisprudence_input_contract() -> None:
    parameters = inspect.signature(LlamaRAGService.explain).parameters

    assert "retrieval" in parameters
    assert "deterministic_evidence" in parameters
    assert "explanation_mode" in parameters
    assert "jurisprudence_retrieval" in parameters


def test_f1_legacy_hypothesis_safety_flags_remain_closed() -> None:
    hypothesis = ControlledLegalHypothesis(
        issue="Determinar una cuestión fiscal preliminar.",
        hypothesis="Hipótesis orientativa sujeta a verificación posterior.",
    )

    assert hypothesis.requires_validation is True
    assert hypothesis.changes_deterministic_result is False
    assert hypothesis.asserts_external_legal_authority is False


def test_f1_orchestration_result_keeps_hypothesis_and_jurisprudence_channels() -> None:
    fields = HybridOrchestrationResult.model_fields

    assert "initial_legal_hypothesis" in fields
    assert "initial_legal_hypothesis_verification" in fields
    assert "session_jurisprudence_result" in fields
    assert "hybrid_coordination" in fields
    assert "explanation" in fields


def test_f1_runtime_constructor_keeps_legacy_hypothesis_optional() -> None:
    parameter = inspect.signature(HybridOrchestrator.__init__).parameters[
        "legal_hypothesis_service"
    ]

    assert parameter.default is None


def test_f1_mock_provider_identity_is_stable() -> None:
    provider = MockLLMProvider()

    assert provider.provider_name == "mock"
    assert provider.model_name == "deterministic-mock"
