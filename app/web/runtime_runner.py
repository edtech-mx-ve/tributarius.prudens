from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.domain.jurisprudence_hybrid import SessionJurisprudenceHybridResult
from app.domain.orchestration import HybridOrchestrationRequest
from app.services.hybrid_jurisprudence_integration import (
    run_hybrid_with_session_jurisprudence,
)
from app.services.hybrid_orchestrator import HybridOrchestrator
from app.services.integral_legal_analyzer import build_integral_legal_analysis
from app.services.traceability import build_canonical_result
from app.web.jurisprudence_session import load_web_jurisprudence_session
from app.web.presenter import (
    present_canonical_result,
    present_integral_legal_analysis,
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
    metadata_by_document_id = {
        item.document_id: item for item in result.applicability
    }
    items: list[dict[str, object | None]] = []
    for hit in result.retrieval.hits:
        assessment = metadata_by_document_id.get(hit.document_id)
        if assessment is None:
            continue
        items.append(
            {
                "ref_id": (
                    f"session-jurisprudence:{hit.document_id}:page:{hit.page_number}"
                ),
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
                "requires_human_review": assessment.requires_human_review,
            }
        )
    return items


@dataclass
class WebHybridRunner:
    """Adaptador web -> orquestador, sin duplicar razonamiento fiscal."""

    orchestrator: HybridOrchestrator
    retrieval_runtime: str
    explanation_runtime: str

    def run(self, request: WebConsultationRequest) -> dict[str, object]:
        session_documents = []
        session_metadata = {}
        if request.jurisprudence_session_id is not None:
            representation, metadata = load_web_jurisprudence_session(
                request.jurisprudence_session_id
            )
            session_documents = [representation]
            session_metadata = {representation.document_id: metadata}

        orchestration_request = HybridOrchestrationRequest(
            query=request.query,
            query_date=date.today(),
            query_fiscal_year=request.fiscal_year,
            top_k=5,
            explanation_mode=_explanation_mode(request.mode),
            session_jurisprudence_documents=session_documents,
            session_jurisprudence_metadata=session_metadata,
        )
        result = run_hybrid_with_session_jurisprudence(
            self.orchestrator,
            orchestration_request,
        )
        canonical = build_canonical_result(orchestration_request, result)
        presented = present_canonical_result(canonical, request)
        integral_analysis = build_integral_legal_analysis(result)
        presented["legal_analysis"] = present_integral_legal_analysis(
            integral_analysis
        )

        if result.session_jurisprudence_result is not None:
            existing = presented.get("evidence")
            evidence = list(existing) if isinstance(existing, list) else []
            evidence.extend(
                _present_session_jurisprudence(result.session_jurisprudence_result)
            )
            presented["evidence"] = evidence
            presented["session_jurisprudence"] = {
                "returned_count": (
                    result.session_jurisprudence_result.retrieval.returned_count
                ),
                "requires_human_review": (
                    result.session_jurisprudence_result.requires_human_review
                ),
                "has_conflict": (
                    result.session_jurisprudence_result.relations.has_conflict
                ),
            }

        presented["runtime"] = {
            "retrieval": self.retrieval_runtime,
            "explanation": self.explanation_runtime,
        }
        return presented
