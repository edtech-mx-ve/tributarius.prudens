from __future__ import annotations

from app.domain.hybrid_integral_legal_analysis import (
    HybridAnalyzerProjection,
    HybridIntegralLegalAnalysis,
)
from app.domain.hybrid_legal_coordination import H1CoordinationDisposition
from app.domain.hybrid_legal_verification import HybridLegalVerificationState
from app.domain.integral_legal_analysis import IntegralLegalAnalysisStatus
from app.domain.integral_legal_readiness import LegalAnalysisReadiness
from app.domain.jurisprudence_decision_application import JurisprudenceDecisionEffect
from app.domain.orchestration import HybridOrchestrationResult
from app.services.integral_legal_analyzer import build_integral_legal_analysis


class HybridIntegralLegalAnalyzerError(ValueError):
    """F.8 no puede consumir una cadena híbrida incompleta o inconsistente."""


def _projection(result: HybridOrchestrationResult) -> HybridAnalyzerProjection:
    verification = result.hybrid_legal_verification
    if verification is None:
        raise HybridIntegralLegalAnalyzerError(
            "F.8 exige el resultado de verificación F.7 antes de construir Analyzer híbrido."
        )

    coordination = result.hybrid_legal_coordination
    if coordination is not None:
        if verification.canonical_conclusion != coordination.canonical_conclusion:
            raise HybridIntegralLegalAnalyzerError(
                "F.8 detectó divergencia entre la conclusión F.6 y la conclusión auditada F.7."
            )
        reasoning_controller = coordination.reasoning_controller
        legal_authority_source = coordination.legal_authority_source
        applicable_normative_refs = list(coordination.applicable_normative_refs)
        h1_disposition = coordination.h1_disposition
        rbs_h1_relation = coordination.rbs_h1_relation
        cbr_h1_effect = coordination.cbr_h1_effect
        jurisprudence_effect = coordination.jurisprudence_effect
        binding_interpretation_required = coordination.binding_interpretation_required
        binding_document_ids = list(coordination.binding_jurisprudence_document_ids)
        binding_evidence_refs = list(coordination.binding_jurisprudence_evidence_refs)
    else:
        reasoning_controller = None
        legal_authority_source = None
        applicable_normative_refs = []
        h1_disposition = H1CoordinationDisposition.NOT_PRESENT
        rbs_h1_relation = None
        cbr_h1_effect = None
        jurisprudence_effect = JurisprudenceDecisionEffect.NO_EFFECT
        binding_interpretation_required = False
        binding_document_ids = []
        binding_evidence_refs = []

    requires_correction = (
        verification.state is HybridLegalVerificationState.CORRECTION_REQUIRED
    )
    requires_human_review = (
        verification.state is HybridLegalVerificationState.HUMAN_REVIEW
    )

    return HybridAnalyzerProjection(
        verification_state=verification.state,
        verification_packet_sha256=verification.packet_sha256,
        canonical_conclusion=verification.canonical_conclusion,
        reasoning_controller=reasoning_controller,
        legal_authority_source=legal_authority_source,
        applicable_normative_refs=applicable_normative_refs,
        h1_hypothesis_id=verification.h1_hypothesis_id,
        h1_disposition=h1_disposition,
        rbs_h1_relation=rbs_h1_relation,
        cbr_h1_effect=cbr_h1_effect,
        h2_ratio_ids=list(verification.h2_ratio_ids),
        jurisprudence_effect=jurisprudence_effect,
        binding_interpretation_required=binding_interpretation_required,
        binding_jurisprudence_document_ids=binding_document_ids,
        binding_jurisprudence_evidence_refs=binding_evidence_refs,
        correction_codes=list(verification.correction_codes),
        review_codes=list(verification.review_codes),
        semantic_verification_performed=verification.semantic_verification_performed,
        requires_correction=requires_correction,
        requires_human_review=requires_human_review,
        analyzer_may_close=(verification.state is HybridLegalVerificationState.VERIFIED),
    )


def _hybrid_status(
    *,
    base_status: IntegralLegalAnalysisStatus,
    verification_state: HybridLegalVerificationState,
) -> IntegralLegalAnalysisStatus:
    if verification_state is HybridLegalVerificationState.VERIFIED:
        return base_status
    return IntegralLegalAnalysisStatus.REVIEW_REQUIRED


def _hybrid_readiness(
    result: HybridOrchestrationResult,
    projection: HybridAnalyzerProjection,
    base_readiness: LegalAnalysisReadiness,
) -> LegalAnalysisReadiness:
    requirements = list(base_readiness.missing_requirements)
    if projection.requires_correction:
        requirements.extend(
            f"hybrid_verification_correction:{code}"
            for code in projection.correction_codes
        )
    if projection.requires_human_review:
        requirements.extend(
            f"hybrid_verification_review:{code}"
            for code in projection.review_codes
        )

    return base_readiness.model_copy(
        update={
            "missing_requirements": list(dict.fromkeys(requirements)),
            "can_close_automatically": bool(
                base_readiness.can_close_automatically
                and projection.analyzer_may_close
            ),
            "requires_human_review": bool(
                base_readiness.requires_human_review
                or result.requires_human_review
                or projection.requires_human_review
            ),
        },
        deep=True,
    )


def build_hybrid_integral_legal_analysis(
    result: HybridOrchestrationResult,
) -> HybridIntegralLegalAnalysis:
    """Construye Analyzer F.8 consumiendo F.7 sin reejecutar fuentes.

    El Analyzer 1.0 se reutiliza como base estructural. Cuando F.7 está
    presente, su conclusión auditada es la única conclusión que F.8 proyecta;
    no existe fallback silencioso a heurísticas, RBS o CBR si F.7 no pudo
    conservar una conclusión canónica.
    """

    projection = _projection(result)
    base = build_integral_legal_analysis(result)

    if (
        projection.verification_state is HybridLegalVerificationState.VERIFIED
        and projection.canonical_conclusion != base.canonical_conclusion
    ):
        raise HybridIntegralLegalAnalyzerError(
            "F.8 VERIFIED no coincide con la conclusión que Analyzer 1.0 "
            "recibió del flujo determinista."
        )

    readiness = _hybrid_readiness(result, projection, base.readiness)
    requires_human_review = bool(
        base.requires_human_review or projection.requires_human_review
    )

    payload = base.model_dump(mode="python")
    payload.update(
        {
            "schema_version": "1.1",
            "source_analyzer_schema_version": base.schema_version,
            "canonical_conclusion": projection.canonical_conclusion,
            "controlling_source": (
                projection.reasoning_controller
                if projection.reasoning_controller is not None
                else None
            ),
            "readiness": readiness,
            "requires_human_review": requires_human_review,
            "status": _hybrid_status(
                base_status=base.status,
                verification_state=projection.verification_state,
            ),
            "hybrid_projection": projection,
            "requires_correction": projection.requires_correction,
            "hybrid_verification_consumed": True,
            "source_results_reexecuted": False,
            "canonical_conclusion_reconstructed": False,
            "creates_second_conclusion": False,
            "legal_decision_created": False,
            "can_control_legal_decision": False,
        }
    )
    return HybridIntegralLegalAnalysis.model_validate(payload)
