from __future__ import annotations

from app.domain.hybrid_coordination import HybridCoordinationResult
from app.domain.legal_hypothesis import ControlledLegalHypothesisResult
from app.domain.legal_hypothesis_verification import (
    LegalHypothesisVerificationResult,
    LegalHypothesisVerificationState,
)
from app.domain.orchestration import OrchestrationStage, StageStatus, StageTrace
from app.domain.rules import RuleEvaluationResult
from app.services.legal_hypothesis_verification import (
    verify_initial_legal_hypothesis,
)


def run_legal_hypothesis_verification_stage(
    initial_hypothesis: ControlledLegalHypothesisResult | None,
    *,
    rule_result: RuleEvaluationResult,
    hybrid_coordination: HybridCoordinationResult | None,
) -> tuple[LegalHypothesisVerificationResult, StageTrace]:
    """Contrasta la hipótesis después del razonamiento determinista."""
    verification = verify_initial_legal_hypothesis(
        initial_hypothesis,
        rule_result=rule_result,
        hybrid_coordination=hybrid_coordination,
    )

    if verification.state == LegalHypothesisVerificationState.NOT_APPLICABLE:
        status = StageStatus.SKIPPED
        detail = "No existe hipótesis inicial que contrastar."
    elif verification.state == LegalHypothesisVerificationState.INCONCLUSIVE:
        status = StageStatus.DEGRADED
        detail = (
            "Hipótesis conservada como no vinculante; no existe una conclusión "
            "determinista suficiente para compararla."
        )
    else:
        status = StageStatus.COMPLETED
        detail = (
            "Hipótesis contrastada contra el resultado determinista sin afirmar "
            "equivalencia semántica ni modificar la decisión jurídica."
        )

    return (
        verification,
        StageTrace(
            stage=OrchestrationStage.LEGAL_HYPOTHESIS_VERIFICATION,
            status=status,
            detail=detail,
        ),
    )
