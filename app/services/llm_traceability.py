from __future__ import annotations

from app.domain.llm_trace import LLMTrace
from llm.models import ExplanationMode, RAGExplanation


def build_llm_trace(
    explanation: RAGExplanation,
    *,
    explanation_mode: ExplanationMode,
) -> LLMTrace:
    answer = explanation.answer
    return LLMTrace(
        provider_name=explanation.provider_name,
        model_name=explanation.model_name,
        explanation_mode=explanation_mode,
        evidence_ids=list(answer.evidence_ids),
        normative_refs=list(answer.normative_refs),
        rule_refs=list(answer.rule_refs),
        calculation_refs=list(answer.calculation_refs),
        cbr_refs=list(answer.cbr_refs),
        jurisprudence_refs=list(answer.jurisprudence_refs),
        generated=explanation.generation_performed,
        requires_human_review=answer.requires_human_review,
        uncertainties=list(answer.uncertainties),
    )
