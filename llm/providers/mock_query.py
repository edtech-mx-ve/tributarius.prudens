from __future__ import annotations

import json

from app.domain.query import QueryIntent


class MockQueryAnalyzerProvider:
    """Proveedor determinista específico para probar el Query Analyzer."""

    @property
    def provider_name(self) -> str:
        return "mock-query-analyzer"

    @property
    def model_name(self) -> str:
        return "deterministic-query-mock"

    def generate_messages_json(
        self,
        messages: list[dict[str, str]],
        *,
        response_schema: dict[str, object],
    ) -> str:
        del response_schema
        user_message = messages[-1]["content"].lower()

        if "isr" in user_message and ("calcular" in user_message or "cálculo" in user_message):
            intent = QueryIntent.CALCULATE_ISR
        elif "iva" in user_message and ("calcular" in user_message or "cálculo" in user_message):
            intent = QueryIntent.CALCULATE_IVA
        elif "jurisprud" in user_message:
            intent = QueryIntent.RELATED_JURISPRUDENCE
        elif "derecho" in user_message:
            intent = QueryIntent.KNOW_RIGHTS
        elif "obligacion" in user_message or "obligación" in user_message:
            intent = QueryIntent.IDENTIFY_OBLIGATIONS
        else:
            intent = QueryIntent.UNKNOWN

        payload: dict[str, object] = {
            "primary_intent": intent.value,
            "secondary_intents": [],
            "facts": [],
            "entities": [],
            "missing_fields": [],
            "ambiguities": [],
            "jurisprudence_requested": intent == QueryIntent.RELATED_JURISPRUDENCE,
            "requires_clarification": intent == QueryIntent.UNKNOWN,
            "requires_human_review": False,
        }
        return json.dumps(payload, ensure_ascii=False)
