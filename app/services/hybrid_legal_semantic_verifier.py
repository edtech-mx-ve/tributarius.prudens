from __future__ import annotations

from pydantic import ValidationError

from app.domain.hybrid_legal_verification import (
    HybridLegalSemanticVerificationDraft,
    HybridLegalVerificationPacket,
)
from app.services.hybrid_legal_verification import (
    hybrid_verification_packet_sha256,
    validate_semantic_verification_draft,
)
from llm.errors import LLMGenerationError, LLMResponseValidationError
from llm.hybrid_compact_contracts import (
    CompactContractError,
    CompactHybridLegalSemanticVerificationDraft,
    compact_verification_response_schema,
    expand_compact_verification,
)
from llm.hybrid_verification_prompting import build_f7_verification_messages
from llm.structured_provider import StructuredMessageProvider


class LlamaHybridLegalVerificationService:
    """Genera sólo la evaluación semántica F.7; no puede alterar resultados previos."""

    def __init__(self, provider: StructuredMessageProvider) -> None:
        self._provider = provider

    def generate(
        self,
        packet: HybridLegalVerificationPacket,
    ) -> HybridLegalSemanticVerificationDraft:
        try:
            packet_sha = hybrid_verification_packet_sha256(packet)
            raw = self._provider.generate_messages_json(
                build_f7_verification_messages(packet, packet_sha256=packet_sha),
                response_schema=compact_verification_response_schema(packet),
            )
        except LLMGenerationError:
            raise
        except Exception as exc:
            raise LLMGenerationError(
                "El proveedor LLM falló al verificar el argumento híbrido F.7."
            ) from exc

        try:
            draft = HybridLegalSemanticVerificationDraft.model_validate_json(raw)
        except ValidationError:
            try:
                compact = (
                    CompactHybridLegalSemanticVerificationDraft.model_validate_json(raw)
                )
                draft = expand_compact_verification(
                    compact,
                    packet=packet,
                    packet_sha256=packet_sha,
                )
            except (ValidationError, CompactContractError) as exc:
                raise LLMResponseValidationError(
                    "La verificación F.7 no satisface el transporte compacto controlado."
                ) from exc

        failures = validate_semantic_verification_draft(packet, draft)
        if failures:
            raise LLMResponseValidationError(
                "La verificación F.7 cruzó la frontera del packet: "
                + ", ".join(failures)
            )
        return draft
