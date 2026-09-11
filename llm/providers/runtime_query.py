from __future__ import annotations

import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain.query import QueryIntent


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

_TAXABLE_BASE_RE = re.compile(
    r"\bbase\s+gravable"
    r"(?:\s+(?:mensual|anual|acumulad[ao]))?"
    r"\s*(?:de|por|es|fue|:)?"
    r"\s*\$?\s*"
    r"([0-9][0-9,]*(?:\.[0-9]{1,2})?)"
)

_PRIOR_PROVISIONAL_PAYMENTS_RE = re.compile(
    r"\bpagos?\s+provisionales?"
    r"(?:\s+de\s+isr)?"
    r"\s*(?:por|de|:)?"
    r"\s*\$?\s*"
    r"([0-9][0-9,]*(?:\.[0-9]{1,2})?)"
)

_ISR_WITHHOLDING_RE = re.compile(
    r"\b(?:"
    r"me\s+han\s+retenido"
    r"|me\s+retuvieron"
    r"|isr\s+retenido"
    r"|retenciones?\s+de\s+isr"
    r")"
    r"\s*(?:por|de|:)?"
    r"\s*\$?\s*"
    r"([0-9][0-9,]*(?:\.[0-9]{1,2})?)"
)


def _append_fact(
    facts: list[dict[str, str]],
    *,
    name: str,
    value: str,
) -> None:
    if any(item["name"] == name for item in facts):
        return

    facts.append(
        {
            "name": name,
            "value": value,
            "origin": "explicit",
        }
    )


def _money_value(raw: str) -> str | None:
    clean = raw.replace(",", "").strip()

    try:
        value = Decimal(clean)
    except (InvalidOperation, ValueError):
        return None

    if value < 0:
        return None

    return format(value, "f")


def _extract_isr_runtime_facts(
    user_message: str,
    facts: list[dict[str, str]],
) -> None:
    folded = _fold(user_message)

    if "persona fisica" in folded:
        _append_fact(
            facts,
            name="taxpayer_type",
            value="individual",
        )
    elif "persona moral" in folded:
        _append_fact(
            facts,
            name="taxpayer_type",
            value="legal_entity",
        )

    years = re.findall(
        r"(?<!\d)(19\d{2}|20\d{2}|21\d{2}|2200)(?!\d)",
        folded,
    )
    if years:
        _append_fact(
            facts,
            name="fiscal_year",
            value=years[-1],
        )

    if (
        "servicios profesionales" in folded
        or "profesional independiente" in folded
        or "profesionista independiente" in folded
        or "actividad profesional" in folded
        or "actividades profesionales" in folded
    ):
        _append_fact(
            facts,
            name="activity",
            value="servicios profesionales independientes",
        )

    if "actividades empresariales y profesionales" in folded:
        _append_fact(
            facts,
            name="fiscal_regime",
            value="actividades empresariales y profesionales",
        )

    month_occurrences = sorted(
        (
            match.start(),
            number,
        )
        for name, number in _MONTHS.items()
        for match in re.finditer(
            rf"(?<![a-z0-9]){name}(?![a-z0-9])",
            folded,
        )
    )
    month = (
        month_occurrences[-1][1]
        if month_occurrences
        else None
    )

    if (
        "mensual" in folded
        or "por ese mes" in folded
        or month is not None
    ):
        _append_fact(
            facts,
            name="isr_period",
            value="monthly",
        )
    elif "anual" in folded:
        _append_fact(
            facts,
            name="isr_period",
            value="annual",
        )

    if month is not None:
        _append_fact(
            facts,
            name="isr_month",
            value=str(month),
        )

    base_match = _TAXABLE_BASE_RE.search(folded)
    if base_match is not None:
        amount = _money_value(
            base_match.group(1)
        )
        if amount is not None:
            _append_fact(
                facts,
                name="taxable_base",
                value=amount,
            )

    if re.search(
        r"\bbase\s+gravable\s+acumulad[ao]\b",
        folded,
    ):
        _append_fact(
            facts,
            name="taxable_base_scope",
            value="year_to_month",
        )

    prior_payments_match = (
        _PRIOR_PROVISIONAL_PAYMENTS_RE.search(folded)
    )
    if prior_payments_match is not None:
        amount = _money_value(
            prior_payments_match.group(1)
        )
        if amount is not None:
            _append_fact(
                facts,
                name="prior_provisional_payments",
                value=amount,
            )

    withholding_match = _ISR_WITHHOLDING_RE.search(
        folded
    )
    if withholding_match is not None:
        amount = _money_value(
            withholding_match.group(1)
        )
        if amount is not None:
            _append_fact(
                facts,
                name="isr_withholding",
                value=amount,
            )

    if (
        "mxn" in folded
        or "pesos mexicanos" in folded
        or "peso mexicano" in folded
    ):
        _append_fact(
            facts,
            name="currency",
            value="MXN",
        )


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
            token in folded
            for token in ("calcular", "calculo", "cuanto", "monto", "tasa", "porcentaje")
        ):
            asks_legal_basis = any(
                token in folded
                for token in (
                    "fundamento",
                    "articulo",
                    "ley",
                    "disposicion",
                    "base legal",
                    "sustento",
                    "vigencia",
                )
            )
            operational_rate = any(
                token in folded
                for token in (
                    "aplicar",
                    "aplica",
                    "operacion",
                    "calcular",
                    "calculo",
                    "cuanto",
                    "monto",
                )
            )
            if asks_legal_basis and not operational_rate:
                return QueryIntent.INTERPRET_PROVISION, [], False
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
        adversarial = any(
            marker in folded
            for marker in (
                "ignora las normas",
                "ignora cualquier restriccion",
                "aunque no tengas una fuente",
                "no muestres evidencia",
                "inventa una norma",
                "inventa una regla",
                "omite la evidencia",
                "salta la temporalidad",
            )
        )
        facts: list[dict[str, str]] = []
        if "iva" in folded:
            _append_fact(
                facts,
                name="matter",
                value="IVA",
            )
        elif "isr" in folded:
            _append_fact(
                facts,
                name="matter",
                value="ISR",
            )

        if intent == QueryIntent.CALCULATE_ISR:
            _extract_isr_runtime_facts(
                user_message,
                facts,
            )

        payload: dict[str, object] = {
            "primary_intent": intent.value,
            "secondary_intents": [item.value for item in secondary],
            "facts": facts,
            "entities": [],
            "missing_fields": [],
            "ambiguities": (
                ["La consulta contiene instrucciones para omitir evidencia o controles."]
                if adversarial
                else []
            ),
            "jurisprudence_requested": jurisprudence_requested,
            "requires_clarification": intent == QueryIntent.UNKNOWN,
            "requires_human_review": adversarial,
        }
        return json.dumps(payload, ensure_ascii=False)
