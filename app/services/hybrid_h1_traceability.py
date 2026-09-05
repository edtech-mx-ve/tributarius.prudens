from __future__ import annotations

from app.domain.hybrid_llama_hypotheses import FiscalHypothesisH1Result
from app.domain.orchestration import (
    OrchestrationStage,
    StageStatus,
    StageTrace,
)


def build_hybrid_h1_generation_trace(
    *,
    service_configured: bool,
    result: FiscalHypothesisH1Result | None,
    generation_failed: bool,
) -> StageTrace | None:
    """Representa en la traza canonica la H1 fiscal F.3 realmente ejecutada."""
    if not service_configured:
        return None

    if generation_failed or result is None:
        return StageTrace(
            stage=OrchestrationStage.LEGAL_HYPOTHESIS,
            status=StageStatus.DEGRADED,
            detail=(
                "La generacion de H1 fiscal F.3 fallo de forma controlada; "
                "el razonamiento determinista permanece disponible."
            ),
        )

    if not result.generation_performed:
        return StageTrace(
            stage=OrchestrationStage.LEGAL_HYPOTHESIS,
            status=StageStatus.SKIPPED,
            detail=(
                "H1 fiscal F.3 no fue generada por sus controles internos; "
                "el razonamiento determinista permanece independiente."
            ),
        )

    if result.hypothesis is None:
        return StageTrace(
            stage=OrchestrationStage.LEGAL_HYPOTHESIS,
            status=StageStatus.DEGRADED,
            detail=(
                "H1 fiscal F.3 reporto generacion sin una hipotesis controlada; "
                "el resultado no se promueve al razonamiento juridico."
            ),
        )

    return StageTrace(
        stage=OrchestrationStage.LEGAL_HYPOTHESIS,
        status=StageStatus.COMPLETED,
        detail=(
            "H1 fiscal F.3 generada como hipotesis no vinculante; "
            "queda sometida a contraste posterior con RBS y CBR."
        ),
    )


def build_hybrid_h1_verification_trace(
    *,
    result: FiscalHypothesisH1Result | None,
    rbs_contrast_present: bool,
    cbr_contrast_present: bool,
    requires_human_review: bool,
) -> StageTrace | None:
    """Resume F.4/F.5 sin confundirlos con la verificacion H1 legada."""
    if (
        result is None
        or not result.generation_performed
        or result.hypothesis is None
    ):
        return None

    if not rbs_contrast_present and not cbr_contrast_present:
        return StageTrace(
            stage=OrchestrationStage.LEGAL_HYPOTHESIS_VERIFICATION,
            status=StageStatus.DEGRADED,
            detail=(
                "H1 fiscal F.3 existe, pero no se produjeron contrastes "
                "RBS/CBR trazables."
            ),
        )

    return StageTrace(
        stage=OrchestrationStage.LEGAL_HYPOTHESIS_VERIFICATION,
        status=(
            StageStatus.DEGRADED
            if requires_human_review
            else StageStatus.COMPLETED
        ),
        detail=(
            "H1 fiscal F.3 contrastada contra los resultados juridicos "
            f"posteriores: RBS={str(rbs_contrast_present).lower()}; "
            f"CBR={str(cbr_contrast_present).lower()}; "
            "H1 permanece sin autoridad para controlar Legal Decision."
        ),
    )
