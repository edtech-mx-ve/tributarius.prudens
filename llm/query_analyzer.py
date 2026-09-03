from __future__ import annotations

from pydantic import ValidationError

from app.domain.query import (
    ExtractedFact,
    MissingField,
    QueryAnalysis,
    QueryAnalysisDraft,
    QueryIntent,
)
from app.services.cbr_orientation import integrate_cbr_orientation
from app.services.focused_normative_rag import build_focused_rag_plan
from app.services.full_corpus_expansion import build_full_corpus_expansion_plan
from app.services.multidimensional_query_analysis import analyze_query_multidimensional
from app.services.normative_ranking import rank_normative_sources
from app.services.primary_source_activation import activate_primary_sources
from app.services.rbs_orientation import integrate_rbs_orientation
from app.services.structural_navigation import build_structural_navigation
from app.services.temporal_control import build_temporal_control_plan
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
        multidimensional = analyze_query_multidimensional(
            normalized_query=normalized,
            primary_intent=draft.primary_intent,
            secondary_intents=draft.secondary_intents,
            facts=draft.facts,
        )
        primary_source_activation = activate_primary_sources(multidimensional)
        rbs_orientation = integrate_rbs_orientation(
            multidimensional, primary_source_activation
        )
        cbr_orientation = integrate_cbr_orientation(
            multidimensional,
            primary_source_activation,
            rbs_orientation,
        )
        normative_ranking = rank_normative_sources(
            multidimensional,
            primary_source_activation,
            rbs_orientation,
            cbr_orientation,
        )
        structural_navigation = build_structural_navigation(normative_ranking)
        focused_rag_plan = build_focused_rag_plan(structural_navigation)
        full_corpus_expansion_plan = build_full_corpus_expansion_plan(
            multidimensional,
            normative_ranking,
            focused_rag_plan,
        )
        temporal_control_plan = build_temporal_control_plan(
            multidimensional,
            normative_ranking,
            focused_rag_plan,
            full_corpus_expansion_plan,
        )
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
            multidimensional=multidimensional,
            primary_source_activation=primary_source_activation,
            rbs_orientation=rbs_orientation,
            cbr_orientation=cbr_orientation,
            normative_ranking=normative_ranking,
            structural_navigation=structural_navigation,
            focused_rag_plan=focused_rag_plan,
            full_corpus_expansion_plan=full_corpus_expansion_plan,
            temporal_control_plan=temporal_control_plan,
        )
