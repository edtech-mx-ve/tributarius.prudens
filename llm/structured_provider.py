from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class StructuredMessageProvider(Protocol):
    @property
    def provider_name(self) -> str:
        ...

    @property
    def model_name(self) -> str:
        ...

    def generate_messages_json(
        self,
        messages: list[dict[str, str]],
        *,
        response_schema: dict[str, object],
    ) -> str:
        ...
