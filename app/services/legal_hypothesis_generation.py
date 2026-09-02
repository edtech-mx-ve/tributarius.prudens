from __future__ import annotations

from pydantic import ValidationError

from app.domain.legal_hypothesis import (
    ControlledLegalHypothesis,
    ControlledLegalHypothesisResult,
)
from app.services.legal_hypothesis_control import (
    LegalHypothesisValidationError,
    validate_controlled_legal_hypothesis,
)
from llm.context import build_controlled_legal_context
from llm.errors import LLMGenerationError, LLMResponseValidationError
from llm.models import ExplanationMode, LLMGenerationContext
from llm.provider import LLMProvider
from rag.retrieval.models import RetrievalResult

_HYPOTHESIS_INSTRUCTIONS = [
    (
        "Formula únicamente una hipótesis jurídica inicial y orientativa; "
        "no emitas una conclusión jurídica definitiva."
    ),
    (
        "Identifica el problema jurídico y los puntos que deben ser verificados "
        "posteriormente por los motores deterministas."
    ),
    (
        "Usa exclusivamente los identificadores de evidencia presentes en el "
        "contexto autorizado y declara toda incertidumbre relevante."
    ),
    (
        "Mantén requires_validation=true, changes_deterministic_result=false y "
        "asserts_external_legal_authority=false."
    ),
]


class LlamaLegalHypothesisService:
    """Genera una hipótesis jurídica LLM sometida a una frontera determinista."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    @staticmethod
    def _context_from_retrieval(
        retrieval: RetrievalResult,
    ) -> LLMGenerationContext:
        context = build_controlled_legal_context(
            retrieval,
            explanation_mode=ExplanationMode.PROFESSIONAL,
        )
        return context.model_copy(
            update={"presentation_instructions": list(_HYPOTHESIS_INSTRUCTIONS)},
            deep=True,
        )

    def generate(
        self,
        retrieval: RetrievalResult,
    ) -> ControlledLegalHypothesisResult:
        """Genera y valida una hipótesis; nunca produce una decisión jurídica."""
        if not retrieval.hits:
            return ControlledLegalHypothesisResult(
                generation_performed=False,
                hypothesis=None,
                authorized_evidence_ids=[],
                requires_human_review=True,
                trace=[
                    "legal_hypothesis:generation_performed=false",
                    "legal_hypothesis:reason=no_authorized_evidence",
                    "legal_hypothesis:requires_validation=true",
                    "legal_hypothesis:deterministic_result_unchanged=true",
                ],
            )

        context = self._context_from_retrieval(retrieval)
        try:
            raw = self._provider.generate_json(
                context,
                response_schema=ControlledLegalHypothesis.model_json_schema(),
            )
        except LLMGenerationError:
            raise
        except Exception as exc:
            raise LLMGenerationError(
                "El proveedor LLM falló al generar la hipótesis jurídica controlada."
            ) from exc

        try:
            hypothesis = ControlledLegalHypothesis.model_validate_json(raw)
        except ValidationError as exc:
            raise LLMResponseValidationError(
                "La hipótesis LLM no satisface el contrato JSON esperado."
            ) from exc

        authorized_ids = [item.chunk_id for item in context.evidence]
        try:
            result = validate_controlled_legal_hypothesis(
                hypothesis,
                authorized_evidence_ids=authorized_ids,
            )
        except LegalHypothesisValidationError as exc:
            raise LLMResponseValidationError(str(exc)) from exc

        return result.model_copy(
            update={
                "trace": [
                    *result.trace,
                    f"legal_hypothesis:provider={self._provider.provider_name}",
                    f"legal_hypothesis:model={self._provider.model_name}",
                    f"legal_hypothesis:evidence_count={len(authorized_ids)}",
                ]
            },
            deep=True,
        )
