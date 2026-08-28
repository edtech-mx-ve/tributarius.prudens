from __future__ import annotations

from pydantic import ValidationError

from llm.errors import LLMGenerationError, LLMResponseValidationError
from llm.models import (
    DeterministicEvidence,
    EvidenceItem,
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
    ) -> LLMGenerationContext:
        evidence = [
            EvidenceItem(
                chunk_id=hit.chunk_id,
                score=hit.score,
                source_type=hit.metadata.source_type,
                source_filename=hit.metadata.source_filename,
                legal_identifier=hit.metadata.legal_identifier,
                page_start=hit.metadata.page_start,
                fiscal_year=hit.metadata.fiscal_year,
                version_label=hit.metadata.version_label,
                text=hit.text,
            )
            for hit in result.hits
        ]
        return LLMGenerationContext(
            question=result.query,
            evidence=evidence,
            deterministic_evidence=deterministic_evidence,
        )

    def explain(
        self,
        retrieval: RetrievalResult,
        *,
        deterministic_evidence: DeterministicEvidence | None = None,
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

        allowed_ids = {item.chunk_id for item in context.evidence}
        invalid_ids = [item for item in answer.evidence_ids if item not in allowed_ids]
        if invalid_ids:
            raise LLMResponseValidationError(
                "La respuesta intentó citar evidencia no recuperada."
            )

        return RAGExplanation(
            question=retrieval.query,
            provider_name=self._provider.provider_name,
            model_name=self._provider.model_name,
            generation_performed=True,
            retrieved_count=len(retrieval.hits),
            answer=answer,
        )
