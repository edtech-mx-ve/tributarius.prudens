from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.domain.hybrid_legal_decision import HybridLegalDecision
from app.domain.hybrid_llama_runtime import HybridLlamaRuntimeResult
from app.domain.integral_legal_analysis import IntegralLegalAnalysis
from app.domain.jurisprudence_hybrid import SessionJurisprudenceHybridResult
from app.domain.legal_decision import LegalDecision
from app.domain.orchestration import (
    HybridOrchestrationRequest,
    HybridOrchestrationResult,
)
from app.services.hybrid_jurisprudence_integration import (
    run_hybrid_with_session_jurisprudence,
)
from app.services.hybrid_llama_runtime import HybridLlamaRuntime
from app.services.hybrid_orchestrator import HybridOrchestrator
from app.services.integral_legal_analyzer import build_integral_legal_analysis
from app.services.legal_decision import build_legal_decision
from app.services.traceability import build_canonical_result
from app.web.jurisprudence_session import (
    load_web_jurisprudence_normative_relation_record,
    load_web_jurisprudence_ratio_record,
    load_web_jurisprudence_session,
    load_web_jurisprudence_temporal_record,
)
from app.web.presenter import (
    present_canonical_result,
    present_integral_legal_analysis,
    present_legal_decision,
)
from app.web.schemas import WebConsultationRequest
from llm.models import ExplanationMode


def _explanation_mode(mode: str) -> ExplanationMode:
    if mode == "taxpayer":
        return ExplanationMode.TAXPAYER
    if mode == "student":
        return ExplanationMode.STUDENT
    return ExplanationMode.PROFESSIONAL


def _present_session_jurisprudence(
    result: SessionJurisprudenceHybridResult,
) -> list[dict[str, object | None]]:
    applicability_by_page = {
        (item.document_id, item.page_number): item for item in result.applicability
    }
    integration_by_ref = {}
    if result.evidence_integration is not None:
        integration_by_ref = {
            item.evidence_ref: item for item in result.evidence_integration.assessments
        }

    items: list[dict[str, object | None]] = []
    for hit in result.retrieval.hits:
        assessment = applicability_by_page.get((hit.document_id, hit.page_number))
        if assessment is None:
            continue
        ref_id = f"session-jurisprudence:{hit.document_id}:page:{hit.page_number}"
        integration = integration_by_ref.get(ref_id)
        if result.evidence_integration is not None and (
            integration is None or not integration.authorized_for_evidence
        ):
            continue
        items.append(
            {
                "ref_id": ref_id,
                "kind": "jurisprudence",
                "role": "jurisprudence",
                "source_type": "jurisprudencia",
                "source_label": "Jurisprudencia temporal",
                "source_reference": hit.original_filename,
                "document_id": hit.document_id,
                "page_start": hit.page_number,
                "page_end": hit.page_number,
                "score": hit.score,
                "snippet": hit.text,
                "applicable_candidate": assessment.applicable_candidate,
                "relation_type": assessment.relation_type.value,
                "authorized_for_evidence": (
                    integration.authorized_for_evidence
                    if integration is not None
                    else assessment.applicable_candidate
                ),
                "evidence_decision": (
                    integration.decision.value if integration is not None else None
                ),
                "requires_human_review": (
                    integration.requires_human_review
                    if integration is not None
                    else assessment.requires_human_review
                ),
            }
        )
    return items


@dataclass
class WebHybridRunner:
    """Adaptador web -> orquestador, sin duplicar razonamiento fiscal."""

    orchestrator: HybridOrchestrator
    retrieval_runtime: str
    explanation_runtime: str
    hybrid_llama_runtime: HybridLlamaRuntime | None = None

    def run(self, request: WebConsultationRequest) -> dict[str, object]:
        session_documents = []
        session_metadata = {}
        session_normative_relations = {}
        session_temporal_records = {}
        session_ratio_records = {}
        if request.jurisprudence_session_id is not None:
            representation, metadata = load_web_jurisprudence_session(
                request.jurisprudence_session_id
            )
            session_documents = [representation]
            session_metadata = {representation.document_id: metadata}
            normative_relation = load_web_jurisprudence_normative_relation_record(
                request.jurisprudence_session_id
            )
            temporal_record = load_web_jurisprudence_temporal_record(
                request.jurisprudence_session_id
            )
            ratio_record = load_web_jurisprudence_ratio_record(
                request.jurisprudence_session_id
            )
            if normative_relation is not None:
                session_normative_relations[representation.document_id] = (
                    normative_relation
                )
            if temporal_record is not None:
                session_temporal_records[representation.document_id] = temporal_record
            if ratio_record is not None:
                session_ratio_records[representation.document_id] = ratio_record

        orchestration_request = HybridOrchestrationRequest(
            query=request.query,
            query_date=date.today(),
            query_fiscal_year=request.fiscal_year,
            top_k=5,
            explanation_mode=_explanation_mode(request.mode),
            session_jurisprudence_documents=session_documents,
            session_jurisprudence_metadata=session_metadata,
            session_jurisprudence_normative_relations=session_normative_relations,
            session_jurisprudence_temporal_records=session_temporal_records,
            session_jurisprudence_ratio_records=session_ratio_records,
        )
        llama_runtime_result: HybridLlamaRuntimeResult | None = None
        result: HybridOrchestrationResult
        integral_analysis: IntegralLegalAnalysis
        legal_decision: LegalDecision | HybridLegalDecision
        if self.hybrid_llama_runtime is None:
            result = run_hybrid_with_session_jurisprudence(
                self.orchestrator,
                orchestration_request,
            )
            integral_analysis = build_integral_legal_analysis(result)
            legal_decision = build_legal_decision(integral_analysis)
        else:
            llama_runtime_result = self.hybrid_llama_runtime.run(orchestration_request)
            result = llama_runtime_result.orchestration
            integral_analysis = llama_runtime_result.analysis
            legal_decision = llama_runtime_result.decision

        canonical = build_canonical_result(orchestration_request, result)
        presented = present_canonical_result(canonical, request)
        presented["legal_analysis"] = present_integral_legal_analysis(integral_analysis)
        presented["legal_decision"] = present_legal_decision(legal_decision)

        if result.session_jurisprudence_result is not None:
            existing = presented.get("evidence")
            evidence = list(existing) if isinstance(existing, list) else []
            evidence.extend(
                _present_session_jurisprudence(result.session_jurisprudence_result)
            )
            presented["evidence"] = evidence
            integration = result.session_jurisprudence_result.evidence_integration
            presented["session_jurisprudence"] = {
                "returned_count": (
                    result.session_jurisprudence_result.retrieval.returned_count
                ),
                "admitted_evidence_count": (
                    integration.admitted_count if integration is not None else None
                ),
                "review_only_count": (
                    integration.review_only_count if integration is not None else None
                ),
                "rejected_count": (
                    integration.rejected_count if integration is not None else None
                ),
                "requires_human_review": (
                    result.session_jurisprudence_result.requires_human_review
                ),
                "has_conflict": (
                    result.session_jurisprudence_result.relations.has_conflict
                ),
                "e6_application": (
                    result.session_jurisprudence_result.decision_application.model_dump(
                        mode="json"
                    )
                    if result.session_jurisprudence_result.decision_application is not None
                    else None
                ),
            }

        runtime_payload: dict[str, object] = {
            "retrieval": self.retrieval_runtime,
            "explanation": self.explanation_runtime,
        }
        if llama_runtime_result is not None:
            runtime_payload.update(
                {
                    "llm_provider": llama_runtime_result.provider_name,
                    "llm_model": llama_runtime_result.model_name,
                    "hybrid_llama_status": llama_runtime_result.status.value,
                    "real_llama": not llama_runtime_result.provider_is_test_double,
                    "h1_generation_attempted": (
                        llama_runtime_result.h1_generation_attempted
                    ),
                    "h2_generation_attempted": (
                        llama_runtime_result.h2_generation_attempted
                    ),
                    "semantic_verification_attempted": (
                        llama_runtime_result.semantic_verification_attempted
                    ),
                }
            )
        presented["runtime"] = runtime_payload
        return presented
