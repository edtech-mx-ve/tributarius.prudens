from __future__ import annotations

import json

from app.domain.llama_hybrid_context import (
    InitialFiscalHypothesisContext,
    JurisprudentialRatioContext,
)
from llm.hybrid_compact_contracts import h1_compact_catalog, h2_compact_catalog

_H1_SYSTEM_PROMPT = (
    "Eres el componente abductivo H1 de Tributarius prudens.\n"
    "Formula una hipótesis fiscal inicial, provisional y no vinculante usando sólo los datos\n"
    "proporcionados. Devuelve JSON breve, sin explicación fuera del objeto. legal_problem\n"
    "debe tener máximo 20 palabras y proposition máximo 35 palabras. Selecciona como máximo\n"
    "4 índices en fact_indices, 1 en institution_indices y 2 en normative_ref_indices. "
    "No inventes hechos, artículos, jurisprudencia, fuentes, fechas ni autoridades. "
    "No emitas una decisión\n"
    "jurídica. No escribas citas jurídicas específicas dentro de legal_problem ni "
    "proposition. No menciones números de artículo, tesis, jurisprudencia, registros "
    "digitales ni identificadores normativos dentro de esos textos. Si una referencia "
    "normativa aparece en selection_catalog, selecciónala exclusivamente mediante "
    "normative_ref_indices y nunca copies esa referencia dentro de proposition. "
    "proposition debe expresar solamente una hipótesis fiscal provisional que requiera "
    "validación normativa posterior. confidence_band sólo puede ser low, medium o high.\n"
)

_H2_SYSTEM_PROMPT = (
    "Eres el componente H2 de ratio decidendi de Tributarius prudens.\n"
    "Reconstruye una hipótesis de ratio sólo desde el catálogo literal de Justificación.\n"
    "Devuelve JSON breve, sin explicación fuera del objeto. legal_question máximo 20 palabras\n"
    "y proposed_ratio máximo 45 palabras. Selecciona entre 1 y 3 support_span_indices y como\n"
    "máximo 2 normative_ref_indices. Si detectas razonamiento accesorio, selecciónalo sólo\n"
    "mediante obiter_span_indices y nunca repitas allí un span de soporte. La ratio es un\n"
    "subconjunto de premisas indispensables que sostiene el Criterio jurídico; "
    "no equipares toda la Justificación con la ratio. Aplica el test contrafactual para\n"
    "distinguir premisas esenciales de razonamiento accesorio. No evalúes aplicabilidad al\n"
    "caso ni alteres la decisión. confidence_band sólo puede ser low, medium o high.\n"
)


def build_h1_messages(context: InitialFiscalHypothesisContext) -> list[dict[str, str]]:
    payload = {
        "task": "formular_h1_fiscal_inicial_controlada",
        "question": context.question,
        "normalized_query": context.normalized_query,
        "primary_intent": context.primary_intent.value,
        "requires_clarification": context.requires_clarification,
        "requires_human_review": context.requires_human_review,
        "primary_problem": {
            "id": context.heuristic_route.primary_problem_id,
            "label": context.heuristic_route.primary_problem_label,
        },
        "selection_catalog": h1_compact_catalog(context),
        "legal_boundary": {
            "requires_later_validation": True,
            "rbs_result_available": False,
            "cbr_result_available": False,
            "jurisprudence_ratio_available": False,
            "can_control_legal_decision": False,
        },
    }
    return [
        {"role": "system", "content": _H1_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        },
    ]


def build_h2_messages(context: JurisprudentialRatioContext) -> list[dict[str, str]]:
    payload = {
        "task": "formular_h2_ratio_decidendi_controlada",
        "document_id": context.document_id,
        "criterion_type": context.criterion_type.value,
        "facts_text": context.facts_text,
        "legal_criterion_text": context.legal_criterion_text,
        "selection_catalog": h2_compact_catalog(context),
        "binding_character_mandatory": context.binding_character_mandatory,
        "ratio_rule": "ratio_subset_of_justification",
        "counterfactual_test_required": True,
        "legal_boundary": {
            "source_section": "justification",
            "requires_later_validation": True,
            "applicability_evaluation_requested": False,
            "external_sources_allowed": False,
            "can_control_legal_decision": False,
        },
    }
    return [
        {"role": "system", "content": _H2_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        },
    ]
