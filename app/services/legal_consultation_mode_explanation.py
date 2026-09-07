from __future__ import annotations

from pydantic import ValidationError

from app.domain.legal_consultation_mode_explanation import (
    LegalConsultationModeExplanation,
)
from app.domain.legal_consultation_query_configuration import (
    LegalConsultationQueryConfiguration,
)
from app.domain.llm_trace import LLMTrace
from app.domain.traceability import CanonicalExecutionResult
from app.services.legal_explanation_profile import (
    get_legal_explanation_profile,
)
from app.services.traceability import verify_canonical_integrity
from llm.models import RAGExplanation


class LegalConsultationModeExplanationError(ValueError):
    """Error de integridad de explicación por modo G.9."""



def build_legal_consultation_mode_explanation(
    canonical: CanonicalExecutionResult,
    query_configuration: LegalConsultationQueryConfiguration,
) -> LegalConsultationModeExplanation:
    """Proyecta explicación ya calculada; nunca vuelve a invocar Llama."""

    if not verify_canonical_integrity(canonical):
        raise LegalConsultationModeExplanationError(
            "G.9 exige un resultado canónico íntegro."
        )

    mode = query_configuration.explanation_mode
    profile = get_legal_explanation_profile(mode)

    explanation_payload = canonical.explanation
    trace_payload = canonical.llm_trace

    if explanation_payload is None:
        if trace_payload is not None:
            raise LegalConsultationModeExplanationError(
                "G.9 detectó traza LLM canónica sin explicación."
            )

        return LegalConsultationModeExplanation(
            mode=mode,
            profile=profile,
            explanation_available=False,
            generation_performed=False,
        )

    if trace_payload is None:
        raise LegalConsultationModeExplanationError(
            "G.9 detectó explicación canónica sin traza LLM."
        )

    try:
        explanation = RAGExplanation.model_validate(explanation_payload)
        llm_trace = LLMTrace.model_validate(trace_payload)
    except ValidationError as exc:
        raise LegalConsultationModeExplanationError(
            "G.9 no pudo validar la explicación canónica de origen."
        ) from exc

    if explanation.question != query_configuration.query:
        raise LegalConsultationModeExplanationError(
            "G.9 detectó una consulta distinta en la explicación canónica."
        )

    if llm_trace.explanation_mode is not mode:
        raise LegalConsultationModeExplanationError(
            "G.9 detectó un modo distinto entre configuración y traza LLM."
        )

    return LegalConsultationModeExplanation(
        mode=mode,
        profile=profile,
        explanation=explanation,
        llm_trace=llm_trace,
        explanation_available=True,
        generation_performed=explanation.generation_performed,
    )
