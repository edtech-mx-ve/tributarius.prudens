from __future__ import annotations

from typing import Protocol

from app.domain.orchestration import (
    HybridOrchestrationRequest,
    HybridOrchestrationResult,
    OrchestrationStage,
    StageStatus,
    StageTrace,
)
from app.services.jurisprudence_applicability import JurisprudenceApplicabilityError
from app.services.jurisprudence_hybrid_stage import run_session_jurisprudence_stage
from app.services.query_fact_compat_19s_r15 import query_fact_value
from jurisprudence.retrieval import JurisprudenceRetrievalError


class HybridOrchestratorLike(Protocol):
    def run(self, request: HybridOrchestrationRequest) -> HybridOrchestrationResult: ...


def run_hybrid_with_session_jurisprudence(
    orchestrator: HybridOrchestratorLike,
    request: HybridOrchestrationRequest,
) -> HybridOrchestrationResult:
    """Integra jurisprudencia temporal sin alterar el resultado determinista base."""

    base_result = orchestrator.run(request)
    if not request.session_jurisprudence_documents:
        return base_result

    try:
        session_result = run_session_jurisprudence_stage(
            query=base_result.analysis.normalized_query,
            documents=request.session_jurisprudence_documents,
            metadata_by_document_id=request.session_jurisprudence_metadata,
            applicable_normative_refs=set(base_result.applicable_normative_refs),
            matter=query_fact_value(base_result.analysis.facts, "matter"),
            top_k=request.top_k,
        )
    except (JurisprudenceRetrievalError, JurisprudenceApplicabilityError):
        return base_result.model_copy(
            update={
                "traces": [
                    *base_result.traces,
                    StageTrace(
                        stage=OrchestrationStage.JURISPRUDENCE,
                        status=StageStatus.DEGRADED,
                        detail=(
                            "La jurisprudencia temporal falló de forma controlada; "
                            "se preservó íntegro el razonamiento híbrido base."
                        ),
                    ),
                ],
                "requires_human_review": True,
            }
        )

    applicable_count = sum(
        item.applicable_candidate for item in session_result.applicability
    )

    return base_result.model_copy(
        update={
            "session_jurisprudence_result": session_result,
            "traces": [
                *base_result.traces,
                StageTrace(
                    stage=OrchestrationStage.JURISPRUDENCE,
                    status=StageStatus.COMPLETED,
                    detail=(
                        "Jurisprudencia temporal evaluada: "
                        f"{session_result.retrieval.returned_count} resultado(s); "
                        f"candidatos aplicables={applicable_count}."
                    ),
                ),
            ],
            "requires_human_review": (
                base_result.requires_human_review
                or session_result.requires_human_review
            ),
        }
    )
