from __future__ import annotations

from typing import Protocol

from app.domain.traceability import CanonicalExecutionResult
from app.web.presenter import present_canonical_result
from app.web.schemas import WebConsultationRequest


class CanonicalEngine(Protocol):
    def run_web_request(
        self,
        request: WebConsultationRequest,
    ) -> CanonicalExecutionResult:
        ...


class CanonicalWebRunner:
    """Adapta un motor canónico configurado al contrato mínimo de la web."""

    def __init__(self, engine: CanonicalEngine) -> None:
        self._engine = engine

    def run(self, request: WebConsultationRequest) -> dict[str, object]:
        canonical = self._engine.run_web_request(request)
        return present_canonical_result(canonical, request)
