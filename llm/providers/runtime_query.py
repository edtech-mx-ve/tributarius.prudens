from __future__ import annotations

import json
import unicodedata
from typing import Any

from app.domain.query import QueryIntent


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


class RuntimeQueryAnalyzerProvider:
    """Clasificador determinista provisional para el runtime previo a Sprint 20.

    Su propósito es evitar que el mock de pruebas decida intenciones de producción.
    No sustituye el analizador semántico Llama previsto para Sprint 20.
    """

    @property
    def provider_name(self) -> str:
        return "runtime-query-analyzer"

    @property
    def model_name(self) -> str:
        return "deterministic-runtime-v1"

    @staticmethod
    def _classify(text: str) -> tuple[QueryIntent, list[QueryIntent], bool]:
        folded = _fold(text)

        explicit_jurisprudence = any(
            token in folded
            for token in (
                "jurisprudencia",
                "tesis aislada",
                "tesis jurisprudencial",
                "precedente judicial",
            )
        )
        if explicit_jurisprudence:
            return QueryIntent.RELATED_JURISPRUDENCE, [], True

        if "isr" in folded and any(
            token in folded for token in ("calcular", "calculo", "cuanto", "monto")
        ):
            return QueryIntent.CALCULATE_ISR, [], False

        if "iva" in folded and any(
            token in folded for token in ("calcular", "calculo", "cuanto", "monto")
        ):
            return QueryIntent.CALCULATE_IVA, [], False

        interpretation_terms = (
            "fundamento",
            "articulo",
            "ley",
            "disposicion",
            "interpret",
            "base legal",
            "sustento",
            "vigencia",
        )
        if any(token in folded for token in interpretation_terms):
            return QueryIntent.INTERPRET_PROVISION, [], False

        if any(token in folded for token in ("obligacion", "debo presentar", "debo pagar")):
            return QueryIntent.IDENTIFY_OBLIGATIONS, [], False

        if any(token in folded for token in ("derecho", "derechos del contribuyente")):
            return QueryIntent.KNOW_RIGHTS, [], False

        if any(
            token in folded
            for token in ("defensa", "impugnar", "recurso", "juicio contencioso")
        ):
            return QueryIntent.DEFENSE_OPTIONS, [], False

        if any(
            token in folded
            for token in ("acto de autoridad", "auditoria", "visita domiciliaria")
        ):
            return QueryIntent.ANALYZE_AUTHORITY_ACT, [], False

        if any(token in folded for token in ("deuda", "incumplimiento", "credito fiscal")):
            return QueryIntent.REVIEW_DEBT_NONCOMPLIANCE, [], False

        if any(token in folded for token in ("caso semejante", "casos similares")):
            return QueryIntent.SIMILAR_CASES, [], False

        if any(token in folded for token in ("aprender", "explica", "que es", "concepto")):
            return QueryIntent.LEARN_TAX_LAW, [], False

        if any(
            token in folded
            for token in (
                "iva",
                "isr",
                "impuesto",
                "contribucion",
                "fiscal",
                "tributario",
            )
        ):
            return QueryIntent.UNDERSTAND_TAX_SYSTEM, [], False

        return QueryIntent.UNKNOWN, [], False

    def generate_messages_json(
        self,
        messages: list[dict[str, str]],
        *,
        response_schema: dict[str, object],
    ) -> str:
        del response_schema
        raw_user_message = messages[-1]["content"]
        try:
            message_payload: Any = json.loads(raw_user_message)
        except json.JSONDecodeError:
            user_message = raw_user_message
        else:
            if isinstance(message_payload, dict) and isinstance(message_payload.get("query"), str):
                user_message = message_payload["query"]
            else:
                user_message = raw_user_message

        intent, secondary, jurisprudence_requested = self._classify(user_message)

        folded = _fold(user_message)
        facts: list[dict[str, str]] = []
        if "iva" in folded:
            facts.append(
                {
                    "name": "matter",
                    "value": "IVA",
                    "origin": "explicit",
                }
            )
        elif "isr" in folded:
            facts.append(
                {
                    "name": "matter",
                    "value": "ISR",
                    "origin": "explicit",
                }
            )

        payload: dict[str, object] = {
            "primary_intent": intent.value,
            "secondary_intents": [item.value for item in secondary],
            "facts": facts,
            "entities": [],
            "missing_fields": [],
            "ambiguities": [],
            "jurisprudence_requested": jurisprudence_requested,
            "requires_clarification": intent == QueryIntent.UNKNOWN,
            "requires_human_review": False,
        }
        return json.dumps(payload, ensure_ascii=False)
