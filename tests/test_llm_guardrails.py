import json

import pytest

from llm.errors import LLMResponseValidationError
from llm.models import DeterministicEvidence, LLMGenerationContext
from llm.service import LlamaRAGService
from tests.test_llm_service import retrieval_with_hit


class GuardrailProvider:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    @property
    def provider_name(self) -> str:
        return "guardrail"

    @property
    def model_name(self) -> str:
        return "guardrail-model"

    def generate_json(
        self,
        context: LLMGenerationContext,
        *,
        response_schema: dict[str, object],
    ) -> str:
        del context, response_schema
        return json.dumps(self.payload, ensure_ascii=False)


def payload(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "summary": "Conclusión explicada.",
        "analysis": "Explicación sin alterar los motores previos.",
        "evidence_ids": ["chunk-0001"],
        "normative_refs": ["NORM-001"],
        "rule_refs": ["RULE-001"],
        "calculation_refs": ["ISR=2300.00"],
        "cbr_refs": ["CASE-001"],
        "jurisprudence_refs": [],
        "uncertainties": [],
        "requires_human_review": False,
        "changes_deterministic_result": False,
        "asserts_external_legal_authority": False,
    }
    value.update(overrides)
    return value


def deterministic() -> DeterministicEvidence:
    return DeterministicEvidence(
        applicable_normative_refs=["NORM-001"],
        rule_conclusions=["RULE-001"],
        calculations=["ISR=2300.00"],
        similar_cases=["CASE-001"],
    )


def test_guardrail_rejects_attempt_to_change_deterministic_result() -> None:
    provider = GuardrailProvider(payload(changes_deterministic_result=True))

    with pytest.raises(LLMResponseValidationError, match="no puede modificar"):
        LlamaRAGService(provider).explain(
            retrieval_with_hit(),
            deterministic_evidence=deterministic(),
        )


def test_guardrail_rejects_external_legal_authority() -> None:
    provider = GuardrailProvider(payload(asserts_external_legal_authority=True))

    with pytest.raises(LLMResponseValidationError, match="autoridad jurídica externa"):
        LlamaRAGService(provider).explain(
            retrieval_with_hit(),
            deterministic_evidence=deterministic(),
        )


def test_guardrail_accepts_explanatory_answer_without_override() -> None:
    result = LlamaRAGService(GuardrailProvider(payload())).explain(
        retrieval_with_hit(),
        deterministic_evidence=deterministic(),
    )

    assert result.answer.changes_deterministic_result is False
    assert result.answer.asserts_external_legal_authority is False


def test_guardrails_apply_even_without_deterministic_evidence_object() -> None:
    provider = GuardrailProvider(
        payload(
            normative_refs=[],
            rule_refs=[],
            calculation_refs=[],
            cbr_refs=[],
            changes_deterministic_result=True,
        )
    )

    with pytest.raises(LLMResponseValidationError, match="no puede modificar"):
        LlamaRAGService(provider).explain(retrieval_with_hit())
