from __future__ import annotations

from pydantic import ValidationError

from llm.context import build_controlled_legal_context
from llm.errors import LLMGenerationError, LLMResponseValidationError
from llm.models import (
    DeterministicEvidence,
    ExplanationMode,
    LlamaStructuredAnswer,
    LLMGenerationContext,
    RAGExplanation,
)
from llm.provider import LLMProvider
from rag.retrieval.models import RetrievalResult


class LlamaRAGService:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    @staticmethod
    def _context_from_retrieval(
        result: RetrievalResult,
        deterministic_evidence: DeterministicEvidence | None = None,
        explanation_mode: ExplanationMode = ExplanationMode.PROFESSIONAL,
        jurisprudence_retrieval: RetrievalResult | None = None,
    ) -> LLMGenerationContext:
        return build_controlled_legal_context(
            result,
            deterministic_evidence=deterministic_evidence,
            explanation_mode=explanation_mode,
            jurisprudence_retrieval=jurisprudence_retrieval,
        )

    @staticmethod
    def _validate_answer_against_context(
        answer: LlamaStructuredAnswer,
        context: LLMGenerationContext,
    ) -> None:
        allowed_ids = {item.chunk_id for item in context.evidence}
        invalid_ids = [item for item in answer.evidence_ids if item not in allowed_ids]
        if invalid_ids:
            raise LLMResponseValidationError(
                "La respuesta intentó citar evidencia no recuperada."
            )

        if answer.changes_deterministic_result:
            raise LLMResponseValidationError(
                "Llama no puede modificar resultados jurídicos o determinísticos."
            )
        if answer.asserts_external_legal_authority:
            raise LLMResponseValidationError(
                "Llama no puede introducir autoridad jurídica externa al contexto."
            )

        deterministic = context.deterministic_evidence
        if deterministic is None:
            return

        allowed_channels = {
            "normative_refs": set(deterministic.applicable_normative_refs)
            | set(deterministic.normative_evidence_refs),
            "rule_refs": set(deterministic.rule_conclusions),
            "calculation_refs": set(deterministic.calculations),
            "cbr_refs": set(deterministic.similar_cases),
            "jurisprudence_refs": set(deterministic.jurisprudential_criteria),
        }
        for field_name, allowed in allowed_channels.items():
            claimed = set(getattr(answer, field_name))
            if not claimed.issubset(allowed):
                raise LLMResponseValidationError(
                    f"La respuesta LLM intentó afirmar {field_name} "
                    "fuera del contexto jurídico autorizado."
                )

        if deterministic.requires_human_review and not answer.requires_human_review:
            raise LLMResponseValidationError(
                "La respuesta LLM no puede eliminar una revisión humana "
                "exigida por la evidencia determinística."
            )

    def explain(
        self,
        retrieval: RetrievalResult,
        *,
        deterministic_evidence: DeterministicEvidence | None = None,
        explanation_mode: ExplanationMode = ExplanationMode.PROFESSIONAL,
        jurisprudence_retrieval: RetrievalResult | None = None,
    ) -> RAGExplanation:
        if not retrieval.hits:
            return RAGExplanation(
                question=retrieval.query,
                provider_name=self._provider.provider_name,
                model_name=self._provider.model_name,
                generation_performed=False,
                retrieved_count=0,
                answer=LlamaStructuredAnswer(
                    summary="No se recuperó evidencia suficiente para responder.",
                    analysis=(
                        "La generación se omitió para evitar una respuesta sin respaldo documental."
                    ),
                    evidence_ids=[],
                    uncertainties=["No hay chunks recuperados para sustentar la respuesta."],
                    requires_human_review=True,
                ),
            )

        context = self._context_from_retrieval(
            retrieval,
            deterministic_evidence=deterministic_evidence,
            explanation_mode=explanation_mode,
            jurisprudence_retrieval=jurisprudence_retrieval,
        )
        try:
            raw = self._provider.generate_json(
                context,
                response_schema=LlamaStructuredAnswer.model_json_schema(),
            )
        except LLMGenerationError:
            raise
        except Exception as exc:
            raise LLMGenerationError("El proveedor LLM falló de forma controlada.") from exc

        try:
            answer = LlamaStructuredAnswer.model_validate_json(raw)
        except ValidationError as exc:
            raise LLMResponseValidationError(
                "La salida LLM no satisface el contrato JSON esperado."
            ) from exc

        self._validate_answer_against_context(answer, context)

        return RAGExplanation(
            question=retrieval.query,
            provider_name=self._provider.provider_name,
            model_name=self._provider.model_name,
            generation_performed=True,
            retrieved_count=len(context.evidence),
            answer=answer,
        )
