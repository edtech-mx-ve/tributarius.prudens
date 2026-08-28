from __future__ import annotations

import json

from llm.models import LLMGenerationContext


class MockLLMProvider:
    """Proveedor determinista para pruebas y degradación controlada."""

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "deterministic-mock"

    def generate_json(
        self,
        context: LLMGenerationContext,
        *,
        response_schema: dict[str, object],
    ) -> str:
        del response_schema
        cited = [item.chunk_id for item in context.evidence[:2]]
        payload = {
            "summary": "Respuesta de prueba basada en evidencia recuperada.",
            "analysis": (
                "El proveedor mock confirma el contrato estructurado sin ejecutar un LLM."
            ),
            "evidence_ids": cited,
            "uncertainties": [],
            "requires_human_review": False,
        }
        return json.dumps(payload, ensure_ascii=False)
