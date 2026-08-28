import json

import pytest

from app.domain.query import QueryIntent
from llm.errors import LLMResponseValidationError
from llm.providers.mock_query import MockQueryAnalyzerProvider
from llm.query_analyzer import QueryAnalyzer


def test_mock_analyzer_detects_isr_and_adds_required_missing_fields() -> None:
    result = QueryAnalyzer(MockQueryAnalyzerProvider()).analyze(
        "Quiero calcular ISR."
    )

    assert result.primary_intent == QueryIntent.CALCULATE_ISR
    assert {item.name for item in result.missing_fields} == {
        "fiscal_year",
        "taxpayer_type",
    }
    assert result.requires_clarification is True


def test_mock_analyzer_marks_jurisprudence_only_when_requested() -> None:
    result = QueryAnalyzer(MockQueryAnalyzerProvider()).analyze(
        "Muéstrame jurisprudencia relacionada."
    )

    assert result.primary_intent == QueryIntent.RELATED_JURISPRUDENCE
    assert result.jurisprudence_requested is True


class InvalidProvider:
    @property
    def provider_name(self) -> str:
        return "invalid"

    @property
    def model_name(self) -> str:
        return "invalid"

    def generate_messages_json(
        self,
        messages: list[dict[str, str]],
        *,
        response_schema: dict[str, object],
    ) -> str:
        del messages, response_schema
        return '{"primary_intent":"not-valid"}'


def test_analyzer_rejects_invalid_structured_output() -> None:
    with pytest.raises(LLMResponseValidationError, match="contrato JSON"):
        QueryAnalyzer(InvalidProvider()).analyze("consulta")


class AuthorityActProvider:
    @property
    def provider_name(self) -> str:
        return "authority"

    @property
    def model_name(self) -> str:
        return "authority"

    def generate_messages_json(
        self,
        messages: list[dict[str, str]],
        *,
        response_schema: dict[str, object],
    ) -> str:
        del messages, response_schema
        return json.dumps(
            {
                "primary_intent": "analyze_authority_act",
                "secondary_intents": [],
                "facts": [],
                "entities": [],
                "missing_fields": [],
                "ambiguities": [],
                "jurisprudence_requested": False,
                "requires_clarification": False,
                "requires_human_review": False,
            }
        )


def test_authority_act_forces_human_review() -> None:
    result = QueryAnalyzer(AuthorityActProvider()).analyze(
        "Recibí un acto de autoridad."
    )

    assert result.requires_human_review is True
