import json

import pytest

from llm.errors import LLMResponseValidationError
from llm.models import DeterministicEvidence, LLMGenerationContext
from llm.service import LlamaRAGService
from tests.test_llm_optional_jurisprudence import jurisprudence_retrieval
from tests.test_llm_service import retrieval_with_hit


class GroundedProvider:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    @property
    def provider_name(self) -> str:
        return "grounded"

    @property
    def model_name(self) -> str:
        return "grounded-model"

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
        "summary": "Conclusión fundada.",
        "analysis": "Análisis limitado a la evidencia autorizada.",
        "evidence_ids": ["chunk-0001"],
        "normative_refs": ["NORM-001"],
        "rule_refs": ["RULE-001"],
        "calculation_refs": ["ISR=2300.00"],
        "cbr_refs": ["CASE-001"],
        "jurisprudence_refs": [],
        "uncertainties": [],
        "requires_human_review": False,
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


@pytest.mark.parametrize(
    ("field_name", "invented"),
    [
        ("normative_refs", ["NORM-INVENTADA"]),
        ("rule_refs", ["RULE-INVENTADA"]),
        ("calculation_refs", ["CALC-INVENTADO"]),
        ("cbr_refs", ["CASE-INVENTADO"]),
        ("jurisprudence_refs", ["JURIS-INVENTADA"]),
    ],
)
def test_generation_rejects_claims_outside_authorized_channels(
    field_name: str,
    invented: list[str],
) -> None:
    provider = GroundedProvider(payload(**{field_name: invented}))

    with pytest.raises(LLMResponseValidationError, match=field_name):
        LlamaRAGService(provider).explain(
            retrieval_with_hit(),
            deterministic_evidence=deterministic(),
        )


def test_generation_accepts_authorized_reasoning_channels() -> None:
    result = LlamaRAGService(GroundedProvider(payload())).explain(
        retrieval_with_hit(),
        deterministic_evidence=deterministic(),
    )

    assert result.answer.normative_refs == ["NORM-001"]
    assert result.answer.rule_refs == ["RULE-001"]
    assert result.answer.calculation_refs == ["ISR=2300.00"]
    assert result.answer.cbr_refs == ["CASE-001"]


def test_generation_accepts_only_supplied_optional_jurisprudence() -> None:
    provider = GroundedProvider(
        payload(
            evidence_ids=["chunk-0001", "juris-chunk-0001"],
            jurisprudence_refs=["juris-chunk-0001"],
        )
    )

    result = LlamaRAGService(provider).explain(
        retrieval_with_hit(),
        deterministic_evidence=deterministic(),
        jurisprudence_retrieval=jurisprudence_retrieval(),
    )

    assert result.answer.jurisprudence_refs == ["juris-chunk-0001"]


def test_generation_cannot_claim_jurisprudence_when_none_was_supplied() -> None:
    provider = GroundedProvider(
        payload(jurisprudence_refs=["juris-chunk-0001"])
    )

    with pytest.raises(LLMResponseValidationError, match="jurisprudence_refs"):
        LlamaRAGService(provider).explain(
            retrieval_with_hit(),
            deterministic_evidence=deterministic(),
        )
