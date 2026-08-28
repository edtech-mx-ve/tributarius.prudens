from __future__ import annotations

from datetime import datetime

from app.domain.orchestration import HybridOrchestrationRequest
from app.domain.traceability import CanonicalExecutionResult
from app.services.hybrid_orchestrator import HybridOrchestrator
from app.services.traceability import build_canonical_result


class TracedHybridOrchestrator:
    """Decorador que produce el resultado canónico sin alterar el motor híbrido."""

    def __init__(self, orchestrator: HybridOrchestrator) -> None:
        self._orchestrator = orchestrator

    def run(
        self,
        request: HybridOrchestrationRequest,
        *,
        now: datetime | None = None,
    ) -> CanonicalExecutionResult:
        result = self._orchestrator.run(request)
        return build_canonical_result(request, result, now=now)
