from __future__ import annotations

from app.domain.legal_consultation_applied_rbs import (
    LegalConsultationAppliedRBS,
)
from app.domain.orchestration import HybridOrchestrationResult
from app.domain.traceability import CanonicalExecutionResult


class LegalConsultationAppliedRBSError(ValueError):
    """Error de integridad del RBS aplicado G.5."""


def build_legal_consultation_applied_rbs(
    result: HybridOrchestrationResult,
    canonical: CanonicalExecutionResult,
) -> LegalConsultationAppliedRBS:
    """Proyecta el RBS ya ejecutado sin volver a evaluar reglas."""

    normalized = result.rbs_reasoning
    if normalized is None:
        raise LegalConsultationAppliedRBSError(
            "G.5 exige un razonamiento RBS previamente normalizado."
        )

    rule_payload = result.rule_result.model_dump(mode="json")
    if canonical.rules != rule_payload:
        raise LegalConsultationAppliedRBSError(
            "G.5 detecto divergencia en las reglas aplicadas canonicas."
        )

    normalized_payload = normalized.model_dump(mode="json")
    if canonical.rbs_reasoning is None:
        raise LegalConsultationAppliedRBSError(
            "G.5 detecto perdida del razonamiento RBS canonico."
        )

    if canonical.rbs_reasoning != normalized_payload:
        raise LegalConsultationAppliedRBSError(
            "G.5 detecto divergencia en el razonamiento RBS canonico."
        )

    controlling_source = None
    if result.hybrid_coordination is not None:
        controlling_source = result.hybrid_coordination.controlling_source
        if controlling_source not in {None, "rbs"}:
            raise LegalConsultationAppliedRBSError(
                "G.5 no permite elevar CBR a fuente controladora juridica."
            )

    return LegalConsultationAppliedRBS(
        rule_evaluation=result.rule_result.model_copy(deep=True),
        normalized_reasoning=normalized.model_copy(deep=True),
        hybrid_controlling_source=(
            "rbs" if controlling_source == "rbs" else None
        ),
    )
