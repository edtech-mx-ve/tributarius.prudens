from __future__ import annotations

from typing import Protocol, runtime_checkable

from llm.models import LLMGenerationContext


@runtime_checkable
class LLMProvider(Protocol):
    @property
    def provider_name(self) -> str:
        ...

    @property
    def model_name(self) -> str:
        ...

    def generate_json(
        self,
        context: LLMGenerationContext,
        *,
        response_schema: dict[str, object],
    ) -> str:
        ...
