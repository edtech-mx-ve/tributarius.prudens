from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.domain.orchestration import HybridOrchestrationRequest
from app.services.hybrid_orchestrator import HybridOrchestrator
from app.services.traceability import build_canonical_result
from app.web.presenter import present_canonical_result
from app.web.schemas import WebConsultationRequest


@dataclass
class WebHybridRunner:
    """Adaptador web -> orquestador, sin duplicar razonamiento fiscal."""

    orchestrator: HybridOrchestrator
    retrieval_runtime: str
    explanation_runtime: str

    def run(self, request: WebConsultationRequest) -> dict[str, object]:
        orchestration_request = HybridOrchestrationRequest(
            query=request.query,
            query_date=date.today(),
            query_fiscal_year=request.fiscal_year,
            top_k=5,
        )
        result = self.orchestrator.run(orchestration_request)
        canonical = build_canonical_result(orchestration_request, result)
        presented = present_canonical_result(canonical, request)
        presented["runtime"] = {
            "retrieval": self.retrieval_runtime,
            "explanation": self.explanation_runtime,
        }
        return presented
