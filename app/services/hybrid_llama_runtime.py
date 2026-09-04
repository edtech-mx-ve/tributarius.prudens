from __future__ import annotations

from dataclasses import dataclass

from app.domain.hybrid_llama_hypotheses import JurisprudentialRatioH2Result
from app.domain.hybrid_llama_runtime import (
    HybridLlamaRuntimeResult,
    HybridLlamaRuntimeStatus,
)
from app.domain.orchestration import HybridOrchestrationRequest, HybridOrchestrationResult
from app.services.hybrid_hypothesis_generation import (
    LlamaFiscalHypothesisH1Service,
    LlamaJurisprudentialRatioH2Service,
)
from app.services.hybrid_integral_legal_analyzer import build_hybrid_integral_legal_analysis
from app.services.hybrid_jurisprudence_integration import run_hybrid_with_session_jurisprudence
from app.services.hybrid_legal_coordination import coordinate_hybrid_legal_argument
from app.services.hybrid_legal_decision import build_hybrid_legal_decision
from app.services.hybrid_legal_semantic_verifier import LlamaHybridLegalVerificationService
from app.services.hybrid_legal_verification import (
    build_hybrid_legal_verification_packet,
    verify_hybrid_legal_argument,
)
from app.services.hybrid_orchestrator import HybridOrchestrator
from llm.errors import LLMError
from llm.structured_provider import StructuredMessageProvider


@dataclass(frozen=True)
class HybridLlamaServiceBundle:
    """Servicios F.3/F.7 construidos sobre un único proveedor estructurado."""

    provider_name: str
    model_name: str
    h1: LlamaFiscalHypothesisH1Service
    h2: LlamaJurisprudentialRatioH2Service
    verifier: LlamaHybridLegalVerificationService


def build_hybrid_llama_service_bundle(
    provider: StructuredMessageProvider,
) -> HybridLlamaServiceBundle:
    """Construye H1, H2 y verificador usando exactamente el mismo proveedor."""

    return HybridLlamaServiceBundle(
        provider_name=provider.provider_name,
        model_name=provider.model_name,
        h1=LlamaFiscalHypothesisH1Service(provider),
        h2=LlamaJurisprudentialRatioH2Service(provider),
        verifier=LlamaHybridLegalVerificationService(provider),
    )


class HybridLlamaRuntime:
    """Ejecuta F.2-F.9 sin convertir al LLM en autoridad jurídica.

    F.10 conecta los contratos ya cerrados. El proveedor se inyecta mediante
    ``StructuredMessageProvider`` para que tests usen dobles deterministas y F.11
    conecte ``LlamaCppProvider`` real sin reescribir la cadena jurídica.
    """

    def __init__(
        self,
        *,
        orchestrator: HybridOrchestrator,
        services: HybridLlamaServiceBundle,
        provider_is_test_double: bool = False,
    ) -> None:
        self._orchestrator = orchestrator
        self._services = services
        self._provider_is_test_double = provider_is_test_double

    def _generate_h2(
        self,
        result: HybridOrchestrationResult,
        failures: list[str],
    ) -> tuple[list[JurisprudentialRatioH2Result], bool]:
        h2_results: list[JurisprudentialRatioH2Result] = []
        attempted = bool(result.llama_jurisprudence_ratio_contexts)
        for context in result.llama_jurisprudence_ratio_contexts:
            try:
                h2_results.append(self._services.h2.generate(context))
            except LLMError:
                failures.append(f"h2_generation_failed:{context.document_id}")
        return h2_results, attempted

    def run(self, request: HybridOrchestrationRequest) -> HybridLlamaRuntimeResult:
        failures: list[str] = []
        base = run_hybrid_with_session_jurisprudence(self._orchestrator, request)

        h1_attempted = self._orchestrator.hybrid_h1_enabled
        if h1_attempted and base.llama_fiscal_hypothesis_h1 is None:
            failures.append("h1_generation_failed")

        h2_results, h2_attempted = self._generate_h2(base, failures)

        jurisprudence_application = None
        if base.session_jurisprudence_result is not None:
            jurisprudence_application = base.session_jurisprudence_result.decision_application

        coordination = coordinate_hybrid_legal_argument(
            applicable_normative_refs=list(base.applicable_normative_refs),
            existing_coordination=base.hybrid_coordination,
            h1_result=base.llama_fiscal_hypothesis_h1,
            rbs_h1_contrast=base.rbs_h1_contrast,
            cbr_h1_contrast=base.cbr_h1_contrast,
            h2_results=h2_results,
            jurisprudence_application=jurisprudence_application,
        )

        packet = build_hybrid_legal_verification_packet(
            coordination=coordination,
            initial_context=base.llama_initial_context,
            h1_result=base.llama_fiscal_hypothesis_h1,
            rbs_h1_contrast=base.rbs_h1_contrast,
            cbr_h1_contrast=base.cbr_h1_contrast,
            h2_results=h2_results,
            jurisprudence_ratio_contexts=list(base.llama_jurisprudence_ratio_contexts),
            jurisprudence_application=jurisprudence_application,
            post_deterministic_context=base.llama_hybrid_review_context,
        )

        semantic_draft = None
        semantic_attempted = coordination.verification_required
        if semantic_attempted:
            try:
                semantic_draft = self._services.verifier.generate(packet)
            except LLMError:
                failures.append("semantic_verification_failed")

        verification = verify_hybrid_legal_argument(
            packet,
            semantic_draft=semantic_draft,
            semantic_verifier_provider=(
                self._services.provider_name if semantic_draft is not None else None
            ),
            semantic_verifier_model=(
                self._services.model_name if semantic_draft is not None else None
            ),
        )

        enriched = base.model_copy(
            update={
                "llama_jurisprudential_ratio_h2": h2_results,
                "hybrid_legal_coordination": coordination,
                "hybrid_legal_verification": verification,
                "requires_human_review": bool(
                    base.requires_human_review
                    or verification.requires_human_review
                    or failures
                ),
            },
            deep=True,
        )
        analysis = build_hybrid_integral_legal_analysis(enriched)
        decision = build_hybrid_legal_decision(analysis)

        unique_failures = list(dict.fromkeys(failures))
        status = (
            HybridLlamaRuntimeStatus.DEGRADED
            if unique_failures
            else HybridLlamaRuntimeStatus.COMPLETED
        )
        return HybridLlamaRuntimeResult(
            status=status,
            provider_name=self._services.provider_name,
            model_name=self._services.model_name,
            orchestration=enriched,
            analysis=analysis,
            decision=decision,
            h1_generation_attempted=h1_attempted,
            h2_generation_attempted=h2_attempted,
            semantic_verification_attempted=semantic_attempted,
            llm_failure_codes=unique_failures,
            provider_is_test_double=self._provider_is_test_double,
        )
