from __future__ import annotations

from typing import NoReturn

from app.domain.orchestration import HybridOrchestrationRequest
from app.web.runtime_runner import WebHybridRunner
from app.web.schemas import WebConsultationRequest


class FakeOrchestrator:
    def run(self, request: HybridOrchestrationRequest) -> NoReturn:
        self.last_request = request
        raise RuntimeError("fixture stops before canonical conversion")


def test_runner_maps_web_request_to_orchestration_request() -> None:
    fake = FakeOrchestrator()
    runner = WebHybridRunner(
        orchestrator=fake,  # type: ignore[arg-type]
        retrieval_runtime="legal_hybrid_19g",
        explanation_runtime="mock",
    )
    request = WebConsultationRequest(
        query="¿Qué dice la Ley del IVA?",
        mode="professional",
        fiscal_year=2026,
    )

    try:
        runner.run(request)
    except RuntimeError as exc:
        assert str(exc) == "fixture stops before canonical conversion"

    assert fake.last_request.query == request.query
    assert fake.last_request.query_fiscal_year == 2026
    assert fake.last_request.top_k == 5
