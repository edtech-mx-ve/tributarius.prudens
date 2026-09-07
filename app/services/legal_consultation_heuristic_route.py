from __future__ import annotations

from app.domain.legal_heuristics import LegalHeuristicEvaluation
from app.domain.orchestration import HybridOrchestrationResult
from app.domain.traceability import CanonicalExecutionResult


class LegalConsultationHeuristicRouteError(ValueError):
    """Error de integridad de la ruta heuristica del reporte G.4."""


def build_legal_consultation_heuristic_route(
    result: HybridOrchestrationResult,
    canonical: CanonicalExecutionResult,
) -> LegalHeuristicEvaluation | None:
    """Proyecta la ruta G.4 ya calculada sin volver a evaluarla."""

    evaluation = result.heuristic_evaluation
    canonical_payload = canonical.legal_heuristics

    if evaluation is None:
        if canonical_payload is not None:
            raise LegalConsultationHeuristicRouteError(
                "G.4 detecto heuristicas canonicas sin evaluacion de origen."
            )
        return None

    if canonical_payload is None:
        raise LegalConsultationHeuristicRouteError(
            "G.4 detecto perdida de la ruta heuristica en el resultado canonico."
        )

    evaluation_payload = evaluation.model_dump(mode="json")
    if evaluation_payload != canonical_payload:
        raise LegalConsultationHeuristicRouteError(
            "G.4 detecto divergencia en la ruta heuristica canonica."
        )

    return evaluation.model_copy(deep=True)
