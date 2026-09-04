from __future__ import annotations

from app.domain.hybrid_integral_legal_analysis import HybridIntegralLegalAnalysis
from app.domain.hybrid_legal_decision import (
    HybridLegalDecision,
    HybridLegalDecisionProjection,
    HybridLegalDecisionStatus,
)
from app.domain.hybrid_legal_verification import HybridLegalVerificationState
from app.domain.integral_legal_analysis import IntegralLegalAnalysisStatus
from app.domain.jurisprudence_decision_application import JurisprudenceDecisionEffect
from app.domain.legal_decision import LegalDecision
from app.services.legal_consequences import build_legal_consequences
from app.services.legal_decision import build_legal_decision
from app.services.legal_reasoning_chain import build_legal_reasoning_chain


class HybridLegalDecisionError(ValueError):
    """F.9 rechaza Analyzer híbrido incompleto o alterado."""


def _validate_analysis_boundary(analysis: HybridIntegralLegalAnalysis) -> None:
    projection = analysis.hybrid_projection

    if analysis.schema_version != "1.1":
        raise HybridLegalDecisionError("F.9 exige Analyzer F.8 schema 1.1.")
    if not analysis.hybrid_verification_consumed:
        raise HybridLegalDecisionError("F.9 exige que F.8 haya consumido F.7.")
    if analysis.canonical_conclusion != projection.canonical_conclusion:
        raise HybridLegalDecisionError(
            "F.9 detectó divergencia entre Analyzer F.8 y su proyección híbrida."
        )
    if projection.verification_state is HybridLegalVerificationState.VERIFIED:
        if projection.reasoning_controller != "rbs":
            raise HybridLegalDecisionError(
                "F.9 exige RBS como controlador del razonamiento verificado."
            )
        if projection.legal_authority_source != "normative_evidence":
            raise HybridLegalDecisionError(
                "F.9 exige la evidencia normativa como fuente de autoridad jurídica."
            )


def _status(analysis: HybridIntegralLegalAnalysis) -> HybridLegalDecisionStatus:
    projection = analysis.hybrid_projection

    if projection.verification_state is HybridLegalVerificationState.CORRECTION_REQUIRED:
        return HybridLegalDecisionStatus.CORRECTION_REQUIRED
    if projection.verification_state is HybridLegalVerificationState.HUMAN_REVIEW:
        return HybridLegalDecisionStatus.HUMAN_REVIEW_REQUIRED
    if analysis.requires_correction:
        return HybridLegalDecisionStatus.CORRECTION_REQUIRED
    if analysis.requires_human_review or analysis.readiness.requires_human_review:
        return HybridLegalDecisionStatus.HUMAN_REVIEW_REQUIRED
    if (
        analysis.status is IntegralLegalAnalysisStatus.INSUFFICIENT_EVIDENCE
        or analysis.canonical_conclusion is None
    ):
        return HybridLegalDecisionStatus.INSUFFICIENT_EVIDENCE
    if (
        analysis.status is IntegralLegalAnalysisStatus.NEEDS_CLARIFICATION
        or analysis.readiness.requires_clarification
    ):
        return HybridLegalDecisionStatus.CONDITIONALLY_DETERMINED
    if not analysis.readiness.can_close_automatically:
        return HybridLegalDecisionStatus.INSUFFICIENT_EVIDENCE
    return HybridLegalDecisionStatus.DETERMINED


def _projection(
    analysis: HybridIntegralLegalAnalysis,
    *,
    status: HybridLegalDecisionStatus,
) -> HybridLegalDecisionProjection:
    source = analysis.hybrid_projection
    closes_automatically = status is HybridLegalDecisionStatus.DETERMINED

    return HybridLegalDecisionProjection(
        source_analysis_schema_version=analysis.schema_version,
        source_verification_packet_sha256=source.verification_packet_sha256,
        verification_state=source.verification_state,
        source_canonical_conclusion=analysis.canonical_conclusion,
        reasoning_controller=source.reasoning_controller,
        legal_authority_source=source.legal_authority_source,
        applicable_normative_refs=list(source.applicable_normative_refs),
        h1_hypothesis_id=source.h1_hypothesis_id,
        h1_disposition=source.h1_disposition,
        rbs_h1_relation=source.rbs_h1_relation,
        cbr_h1_effect=source.cbr_h1_effect,
        h2_ratio_ids=list(source.h2_ratio_ids),
        jurisprudence_effect=source.jurisprudence_effect,
        binding_interpretation_required=source.binding_interpretation_required,
        binding_interpretation=(
            "jurisprudence"
            if source.jurisprudence_effect
            is JurisprudenceDecisionEffect.GOVERNING_INTERPRETATION
            else None
        ),
        binding_jurisprudence_document_ids=list(
            source.binding_jurisprudence_document_ids
        ),
        binding_jurisprudence_evidence_refs=list(
            source.binding_jurisprudence_evidence_refs
        ),
        correction_codes=list(source.correction_codes),
        review_codes=list(source.review_codes),
        requires_correction=analysis.requires_correction,
        requires_human_review=analysis.requires_human_review,
        closes_automatically=closes_automatically,
    )


def _formalized_conclusion(
    analysis: HybridIntegralLegalAnalysis,
    status: HybridLegalDecisionStatus,
) -> str | None:
    if status in {
        HybridLegalDecisionStatus.DETERMINED,
        HybridLegalDecisionStatus.CONDITIONALLY_DETERMINED,
    }:
        return analysis.canonical_conclusion
    return None


def _authority_source(status: HybridLegalDecisionStatus) -> str | None:
    if status in {
        HybridLegalDecisionStatus.DETERMINED,
        HybridLegalDecisionStatus.CONDITIONALLY_DETERMINED,
    }:
        return "normative_evidence"
    return None


def build_hybrid_legal_decision(
    analysis: HybridIntegralLegalAnalysis,
) -> HybridLegalDecision:
    """Formaliza F.8 sin reejecutar H1/H2, RBS, CBR, E.6 o F.7.

    Cuando F.8 no autoriza el cierre, F.9 conserva la conclusión fuente sólo en
    la proyección de trazabilidad y deja ``conclusion=None`` para impedir una
    falsa determinación. Una jurisprudencia obligatoria aplicable gobierna la
    interpretación, pero nunca sustituye la base normativa ni crea otra
    conclusión.
    """

    if not isinstance(analysis, HybridIntegralLegalAnalysis):
        raise HybridLegalDecisionError("F.9 sólo acepta HybridIntegralLegalAnalysis F.8.")

    _validate_analysis_boundary(analysis)
    status = _status(analysis)
    projection = _projection(analysis, status=status)

    legacy = build_legal_decision(analysis)
    conclusion = _formalized_conclusion(analysis, status)
    controlling_source = _authority_source(status)
    requires_human_review = status is HybridLegalDecisionStatus.HUMAN_REVIEW_REQUIRED

    shell = LegalDecision.model_validate(
        {
            **legacy.model_dump(mode="python"),
            "source_analysis_schema_version": analysis.schema_version,
            "applicable_normative_refs": list(projection.applicable_normative_refs),
            "conclusion": conclusion,
            "controlling_source": controlling_source,
            "requires_human_review": requires_human_review,
        }
    )
    shell.reasoning_chain = build_legal_reasoning_chain(shell)
    shell.consequences = build_legal_consequences(shell)

    payload = shell.model_dump(mode="python")
    payload.update(
        {
            "schema_version": "1.1",
            "source_analysis_schema_version": analysis.schema_version,
            "source_legacy_decision_schema_version": legacy.schema_version,
            "status": status,
            "requires_correction": analysis.requires_correction,
            "requires_human_review": requires_human_review,
            "hybrid_projection": projection,
            "hybrid_analysis_consumed": True,
            "source_results_reexecuted": False,
            "canonical_conclusion_reconstructed": False,
            "creates_second_conclusion": False,
            "legal_authority_reassigned_by_llm": False,
        }
    )
    return HybridLegalDecision.model_validate(payload)
