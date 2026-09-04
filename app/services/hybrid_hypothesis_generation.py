from __future__ import annotations

from pydantic import ValidationError

from app.domain.hybrid_llama_hypotheses import (
    FiscalHypothesisH1Draft,
    FiscalHypothesisH1Result,
    JurisprudentialRatioH2Draft,
    JurisprudentialRatioH2Result,
)
from app.domain.llama_hybrid_context import (
    InitialFiscalHypothesisContext,
    JurisprudentialRatioContext,
)
from app.services.hybrid_hypothesis_control import (
    HybridHypothesisValidationError,
    validate_fiscal_hypothesis_h1,
    validate_jurisprudential_ratio_h2,
)
from llm.errors import LLMGenerationError, LLMResponseValidationError
from llm.hybrid_compact_contracts import (
    CompactContractError,
    CompactFiscalHypothesisH1Draft,
    CompactJurisprudentialRatioH2Draft,
    expand_compact_h1,
    expand_compact_h2,
    h1_compact_response_schema,
    h2_compact_response_schema,
)
from llm.hybrid_hypothesis_prompting import build_h1_messages, build_h2_messages
from llm.structured_provider import StructuredMessageProvider


class LlamaFiscalHypothesisH1Service:
    """Formula H1 desde contexto temprano F.2 sin consumir RAG/RBS/CBR finales."""

    def __init__(self, provider: StructuredMessageProvider) -> None:
        self._provider = provider

    def generate(
        self,
        context: InitialFiscalHypothesisContext,
    ) -> FiscalHypothesisH1Result:
        try:
            raw = self._provider.generate_messages_json(
                build_h1_messages(context),
                response_schema=h1_compact_response_schema(context),
            )
        except LLMGenerationError:
            raise
        except Exception as exc:
            raise LLMGenerationError(
                "El proveedor LLM falló al formular H1 fiscal."
            ) from exc

        try:
            draft = FiscalHypothesisH1Draft.model_validate_json(raw)
        except ValidationError:
            try:
                compact = CompactFiscalHypothesisH1Draft.model_validate_json(raw)
                draft = expand_compact_h1(compact, context=context)
            except (ValidationError, CompactContractError) as exc:
                raise LLMResponseValidationError(
                    "H1 no satisface el transporte compacto ni el contrato F.3."
                ) from exc

        try:
            result = validate_fiscal_hypothesis_h1(
                draft,
                context=context,
                provider_name=self._provider.provider_name,
                model_name=self._provider.model_name,
            )
        except HybridHypothesisValidationError as exc:
            raise LLMResponseValidationError(str(exc)) from exc

        return result.model_copy(
            update={
                "trace": [
                    *result.trace,
                    f"f3:h1:provider={self._provider.provider_name}",
                    f"f3:h1:model={self._provider.model_name}",
                ]
            },
            deep=True,
        )


class LlamaJurisprudentialRatioH2Service:
    """Formula H2 sólo desde la Justificación estructurada y trazable de E/F.2."""

    def __init__(self, provider: StructuredMessageProvider) -> None:
        self._provider = provider

    def generate(
        self,
        context: JurisprudentialRatioContext,
    ) -> JurisprudentialRatioH2Result:
        try:
            raw = self._provider.generate_messages_json(
                build_h2_messages(context),
                response_schema=h2_compact_response_schema(context),
            )
        except LLMGenerationError:
            raise
        except Exception as exc:
            raise LLMGenerationError(
                "El proveedor LLM falló al formular H2 jurisprudencial."
            ) from exc

        try:
            draft = JurisprudentialRatioH2Draft.model_validate_json(raw)
        except ValidationError:
            try:
                compact = CompactJurisprudentialRatioH2Draft.model_validate_json(raw)
                draft = expand_compact_h2(compact, context=context)
            except (ValidationError, CompactContractError) as exc:
                raise LLMResponseValidationError(
                    "H2 no satisface el transporte compacto ni el contrato F.3."
                ) from exc

        try:
            result = validate_jurisprudential_ratio_h2(
                draft,
                context=context,
                provider_name=self._provider.provider_name,
                model_name=self._provider.model_name,
            )
        except HybridHypothesisValidationError as exc:
            raise LLMResponseValidationError(str(exc)) from exc

        return result.model_copy(
            update={
                "trace": [
                    *result.trace,
                    f"f3:h2:provider={self._provider.provider_name}",
                    f"f3:h2:model={self._provider.model_name}",
                ]
            },
            deep=True,
        )
