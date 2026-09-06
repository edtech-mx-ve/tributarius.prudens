import unicodedata

from app.domain.llama_hybrid_context import (
    InitialFiscalHypothesisContext,
    LlamaHeuristicRouteContext,
)
from app.domain.query import QueryIntent
from llm.hybrid_compact_contracts import h1_compact_response_schema
from llm.hybrid_hypothesis_prompting import build_h1_messages


def _ascii(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(
        char
        for char in normalized
        if not unicodedata.combining(char)
    )


def test_h1_prompt_forbids_explicit_legal_citations() -> None:
    context = InitialFiscalHypothesisContext(
        question="Consulta fiscal",
        normalized_query="consulta fiscal",
        primary_intent=QueryIntent.IDENTIFY_OBLIGATIONS,
        facts=[],
        heuristic_route=LlamaHeuristicRouteContext(
            primary_problem_id="cumplimiento_fiscal",
            primary_problem_label="Cumplimiento fiscal",
            exact_normative_hints=["lisr:articulo_100"],
        ),
        requires_clarification=False,
        requires_human_review=False,
    )

    messages = build_h1_messages(context)
    system = _ascii(messages[0]["content"])

    assert "No escribas citas juridicas especificas" in system
    assert "normative_ref_indices" in system
    assert "numeros de articulo" in system
    assert "validacion normativa posterior" in system

    schema = h1_compact_response_schema(context)
    proposition = schema["properties"]["proposition"]
    description = _ascii(proposition.get("description", ""))

    assert "sin citas juridicas especificas" in description
    assert "normative_ref_indices" in description
