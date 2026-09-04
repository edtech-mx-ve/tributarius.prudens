from __future__ import annotations

import json

from evaluation.hybrid_llama_fixtures import (
    F12ReferenceStructuredProvider,
    build_f12_request,
    build_f12_runtime,
)
from llm.models import LLMGenerationContext
from llm.rag_compact_contracts import CompactRAGExplanationDraft


class CompactRAGRealLikeProvider(F12ReferenceStructuredProvider):
    def __init__(self) -> None:
        self.tasks: list[str] = []
        self.schemas: list[dict[str, object]] = []

    @property
    def provider_name(self) -> str:
        return "llama-cpp-python"

    @property
    def model_name(self) -> str:
        return "Llama-3.2-1B-Instruct-Q4_K_M"

    def generate_json(
        self,
        context: LLMGenerationContext,
        *,
        response_schema: dict[str, object],
    ) -> str:
        raise AssertionError("Llama real debe usar transporte RAG compacto.")

    def generate_messages_json(
        self,
        messages: list[dict[str, str]],
        *,
        response_schema: dict[str, object],
    ) -> str:
        payload = json.loads(messages[-1]["content"])
        self.tasks.append(str(payload["task"]))
        self.schemas.append(response_schema)
        return super().generate_messages_json(
            messages,
            response_schema=response_schema,
        )


def test_f12_7_real_llama_uses_compact_rag_transport() -> None:
    provider = CompactRAGRealLikeProvider()
    runtime = build_f12_runtime(provider, provider_is_test_double=False)

    result = runtime.run(build_f12_request(with_jurisprudence=False))

    assert result.status.value == "completed"
    assert "explicar_rag_controlado_compacto" in provider.tasks
    rag_index = provider.tasks.index("explicar_rag_controlado_compacto")
    assert provider.schemas[rag_index]["title"] == "CompactRAGExplanationDraft"
    assert result.orchestration.explanation is not None
    assert result.orchestration.explanation.answer.changes_deterministic_result is False
    assert result.orchestration.requires_human_review is False


def test_f12_7_compact_contract_does_not_expose_authority_override_flags() -> None:
    schema = CompactRAGExplanationDraft.model_json_schema()
    properties = schema["properties"]
    assert isinstance(properties, dict)
    assert "changes_deterministic_result" not in properties
    assert "asserts_external_legal_authority" not in properties
