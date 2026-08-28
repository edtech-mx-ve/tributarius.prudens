from __future__ import annotations

from pydantic import ValidationError

from app.domain.query import (
    ExtractedFact,
    MissingField,
    QueryAnalysis,
    QueryAnalysisDraft,
    QueryIntent,
)
from llm.errors import LLMGenerationError, LLMResponseValidationError
from llm.query_prompting import build_query_analysis_messages, normalize_query_text
from llm.structured_provider import StructuredMessageProvider

_REQUIRED_FACTS_BY_INTENT: dict[QueryIntent, tuple[str, ...]] = {
    QueryIntent.CALCULATE_ISR: ("fiscal_year", "taxpayer_type"),
    QueryIntent.CALCULATE_IVA: ("fiscal_year", "taxpayer_type"),
}

_HIGH_REVIEW_INTENTS = {
    QueryIntent.ANALYZE_AUTHORITY_ACT,
    QueryIntent.DEFENSE_OPTIONS,
}


class QueryAnalyzer:
    def __init__(self, provider: StructuredMessageProvider) -> None:
        self._provider = provider

    @staticmethod
    def _fact_names(facts: list[ExtractedFact]) -> set[str]:
        return {fact.name.strip().lower() for fact in facts}

    @classmethod
    def _enforce_deterministic_requirements(
        cls,
        draft: QueryAnalysisDraft,
    ) -> QueryAnalysisDraft:
        fact_names = cls._fact_names(draft.facts)
        missing_names = {item.name.strip().lower() for item in draft.missing_fields}

        for required in _REQUIRED_FACTS_BY_INTENT.get(draft.primary_intent, ()):
            if required not in fact_names and required not in missing_names:
                draft.missing_fields.append(
                    MissingField(
                        name=required,
                        reason=(
                            "Dato mínimo requerido para realizar el cálculo "
                            "de forma reproducible."
                        ),
                    )
                )
                missing_names.add(required)

        if draft.missing_fields:
            draft.requires_clarification = True

        if draft.primary_intent in _HIGH_REVIEW_INTENTS:
            draft.requires_human_review = True

        if draft.primary_intent == QueryIntent.RELATED_JURISPRUDENCE:
            draft.jurisprudence_requested = True

        return draft

    def analyze(self, query: str) -> QueryAnalysis:
        normalized = normalize_query_text(query)
        try:
            raw = self._provider.generate_messages_json(
                build_query_analysis_messages(normalized),
                response_schema=QueryAnalysisDraft.model_json_schema(),
            )
        except LLMGenerationError:
            raise
        except Exception as exc:
            raise LLMGenerationError(
                "El proveedor LLM falló durante el análisis de la consulta."
            ) from exc

        try:
            draft = QueryAnalysisDraft.model_validate_json(raw)
        except ValidationError as exc:
            raise LLMResponseValidationError(
                "La salida del Query Analyzer no satisface el contrato JSON."
            ) from exc

        draft = self._enforce_deterministic_requirements(draft)
        return QueryAnalysis(
            original_query=query,
            normalized_query=normalized,
            primary_intent=draft.primary_intent,
            secondary_intents=draft.secondary_intents,
            facts=draft.facts,
            entities=draft.entities,
            missing_fields=draft.missing_fields,
            ambiguities=draft.ambiguities,
            jurisprudence_requested=draft.jurisprudence_requested,
            requires_clarification=draft.requires_clarification,
            requires_human_review=draft.requires_human_review,
        )
