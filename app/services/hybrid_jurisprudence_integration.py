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
from app.services.jurisprudence_decision_application import (
    evaluate_jurisprudence_for_legal_decision,
)
from app.services.jurisprudence_evidence_integration import (
    JurisprudenceEvidenceIntegrationError,
)
from app.services.jurisprudence_hybrid_stage import run_session_jurisprudence_stage
from app.services.llama_hybrid_context import (
    build_jurisprudential_ratio_contexts,
    build_post_deterministic_hybrid_review_context,
)
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
            normative_relation_records=(
                request.session_jurisprudence_normative_relations
            ),
            temporal_records=request.session_jurisprudence_temporal_records,
            ratio_records=request.session_jurisprudence_ratio_records,
            query_date=request.query_date,
        )
    except (
        JurisprudenceRetrievalError,
        JurisprudenceApplicabilityError,
        JurisprudenceEvidenceIntegrationError,
    ):
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

    decision_application = evaluate_jurisprudence_for_legal_decision(
        analysis=base_result.analysis,
        session_result=session_result,
        ratio_records=request.session_jurisprudence_ratio_records,
        normative_relation_records=request.session_jurisprudence_normative_relations,
    )
    e6_requires_review = (
        decision_application.requires_human_review
        if decision_application.assessments
        else session_result.requires_human_review
    )
    session_result = session_result.model_copy(
        update={
            "decision_application": decision_application,
            "requires_human_review": e6_requires_review,
        }
    )

    applicable_count = sum(
        item.applicable_candidate for item in session_result.applicability
    )
    admitted_count = (
        session_result.evidence_integration.admitted_count
        if session_result.evidence_integration is not None
        else len(session_result.evidence)
    )

    ratio_contexts = build_jurisprudential_ratio_contexts(
        session_result=session_result,
        ratio_records=request.session_jurisprudence_ratio_records,
        normative_relation_records=request.session_jurisprudence_normative_relations,
        temporal_records=request.session_jurisprudence_temporal_records,
    )
    augmented = base_result.model_copy(
        update={
            "session_jurisprudence_result": session_result,
            "llama_jurisprudence_ratio_contexts": ratio_contexts,
            "traces": [
                *base_result.traces,
                StageTrace(
                    stage=OrchestrationStage.JURISPRUDENCE,
                    status=StageStatus.COMPLETED,
                    detail=(
                        "Jurisprudencia temporal evaluada: "
                        f"{session_result.retrieval.returned_count} resultado(s); "
                        f"candidatos previos={applicable_count}; "
                        f"evidencia E.5 admitida={admitted_count}; "
                        f"aplicación E.6={len(decision_application.applicable_document_ids)}."
                    ),
                ),
            ],
            "requires_human_review": (
                base_result.requires_human_review
                or session_result.requires_human_review
            ),
        }
    )
    return augmented.model_copy(
        update={
            "llama_hybrid_review_context": (
                build_post_deterministic_hybrid_review_context(augmented)
            )
        }
    )
