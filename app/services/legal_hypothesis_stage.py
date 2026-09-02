from __future__ import annotations

from typing import Protocol

from app.domain.legal_hypothesis import ControlledLegalHypothesisResult
from app.domain.orchestration import OrchestrationStage, StageStatus, StageTrace
from llm.errors import LLMError
from rag.retrieval.models import RetrievalResult


class LegalHypothesisGeneratorLike(Protocol):
    def generate(
        self,
        retrieval: RetrievalResult,
    ) -> ControlledLegalHypothesisResult: ...


def run_legal_hypothesis_stage(
    service: LegalHypothesisGeneratorLike | None,
    retrieval: RetrievalResult,
) -> tuple[ControlledLegalHypothesisResult | None, StageTrace]:
    """Ejecuta la hipótesis inicial sin concederle autoridad sobre el análisis."""
    if service is None:
        return (
            None,
            StageTrace(
                stage=OrchestrationStage.LEGAL_HYPOTHESIS,
                status=StageStatus.SKIPPED,
                detail=(
                    "Hipótesis jurídica inicial omitida; el análisis determinista "
                    "continúa sin alteraciones."
                ),
            ),
        )

    try:
        result = service.generate(retrieval)
    except LLMError:
        return (
            None,
            StageTrace(
                stage=OrchestrationStage.LEGAL_HYPOTHESIS,
                status=StageStatus.DEGRADED,
                detail=(
                    "Llama no pudo formular la hipótesis inicial; el fallo no "
                    "modifica ni bloquea el análisis jurídico determinista."
                ),
            ),
        )

    if not result.generation_performed:
        return (
            result,
            StageTrace(
                stage=OrchestrationStage.LEGAL_HYPOTHESIS,
                status=StageStatus.SKIPPED,
                detail=(
                    "No se formuló hipótesis por falta de evidencia autorizada; "
                    "el análisis determinista conserva plena independencia."
                ),
            ),
        )

    return (
        result,
        StageTrace(
            stage=OrchestrationStage.LEGAL_HYPOTHESIS,
            status=StageStatus.COMPLETED,
            detail=(
                "Hipótesis jurídica inicial formulada como propuesta no vinculante; "
                "requiere validación por las etapas jurídicas posteriores."
            ),
        ),
    )
