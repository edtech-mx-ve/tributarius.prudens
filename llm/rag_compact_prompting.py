from __future__ import annotations

import json

from llm.models import LLMGenerationContext
from llm.rag_compact_contracts import rag_compact_catalog

_SYSTEM_PROMPT = (
    "Eres el componente explicativo de Tributarius prudens.\n"
    "Explica sin redecidir. Usa únicamente la evidencia y los catálogos autorizados.\n"
    "Devuelve JSON breve. summary máximo 25 palabras y analysis máximo 70 palabras.\n"
    "Para citar, selecciona índices; nunca copies ni inventes ids, normas o resultados.\n"
    "Si existe incertidumbre material usa uncertainty_note y requires_human_review=true.\n"
    "No cambies resultados deterministas ni introduzcas autoridad jurídica externa.\n"
)


def build_compact_rag_messages(context: LLMGenerationContext) -> list[dict[str, str]]:
    evidence = [
        {
            "index": index,
            "source_type": item.source_type.value,
            "legal_identifier": item.legal_identifier,
            "page_start": item.page_start,
            "text": " ".join(item.text.split())[:2200],
        }
        for index, item in enumerate(context.evidence)
    ]
    payload = {
        "task": "explicar_rag_controlado_compacto",
        "question": context.question,
        "explanation_mode": context.explanation_mode.value,
        "evidence": evidence,
        "selection_catalog": rag_compact_catalog(context),
        "deterministic_summary": (
            {
                "hybrid_conclusion": context.deterministic_evidence.hybrid_conclusion,
                "hybrid_controlling_source": (
                    context.deterministic_evidence.hybrid_controlling_source
                ),
                "hybrid_relation": context.deterministic_evidence.hybrid_relation,
                "requires_human_review": (
                    context.deterministic_evidence.requires_human_review
                ),
            }
            if context.deterministic_evidence is not None
            else None
        ),
    }
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        },
    ]
