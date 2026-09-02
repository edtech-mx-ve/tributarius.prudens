from __future__ import annotations

from app.domain.hybrid_coordination import HybridCoordinationResult
from app.domain.legal_heuristics import LegalHeuristicEvaluation
from app.domain.orchestration import OrchestrationStage, StageStatus, StageTrace
from app.services.legal_heuristics import evaluate_legal_heuristics


def run_legal_heuristics_stage(
    coordination: HybridCoordinationResult | None,
) -> tuple[LegalHeuristicEvaluation | None, StageTrace, bool]:
    """Integra heurísticas explícitas sin recalcular la decisión jurídica híbrida."""
    if coordination is None:
        return (
            None,
            StageTrace(
                stage=OrchestrationStage.LEGAL_HEURISTICS,
                status=StageStatus.SKIPPED,
                detail=(
                    "Heurísticas jurídicas omitidas porque no existe "
                    "coordinación RBS-CBR."
                ),
            ),
            False,
        )

    evaluation = evaluate_legal_heuristics(coordination)
    return (
        evaluation,
        StageTrace(
            stage=OrchestrationStage.LEGAL_HEURISTICS,
            status=(
                StageStatus.DEGRADED
                if evaluation.requires_review
                else StageStatus.COMPLETED
            ),
            detail=(
                "Heurísticas jurídicas explícitas: "
                f"{len(evaluation.signals)} señales; "
                f"revisión={'sí' if evaluation.requires_review else 'no'}; "
                "conclusión canónica preservada."
            ),
        ),
        evaluation.requires_review,
    )
