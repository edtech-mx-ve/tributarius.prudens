from __future__ import annotations

from typing import Protocol

from app.security.input_guard import assess_prompt_injection
from app.web.schemas import WebConsultationRequest, WebConsultationResponse


class ConsultationRunner(Protocol):
    def run(self, request: WebConsultationRequest) -> dict[str, object]:
        ...


class WebConsultationService:
    """Frontera web: valida entrada y delega; no duplica razonamiento fiscal."""

    def __init__(self, runner: ConsultationRunner | None = None) -> None:
        self._runner = runner

    def consult(self, request: WebConsultationRequest) -> WebConsultationResponse:
        assessment = assess_prompt_injection(request.query)
        if assessment.suspicious:
            return WebConsultationResponse(
                status="error",
                message=(
                    "La consulta contiene instrucciones incompatibles con el "
                    "uso seguro del sistema. Reformúlala como una pregunta fiscal."
                ),
            )

        if self._runner is None:
            return WebConsultationResponse(
                status="not_configured",
                message=(
                    "El motor de consulta aún no está conectado al runtime web. "
                    "La interfaz está operativa sin simular una respuesta fiscal."
                ),
            )
        try:
            result = self._runner.run(request)
        except (ValueError, RuntimeError):
            return WebConsultationResponse(
                status="error",
                message="La consulta no pudo procesarse de forma segura.",
            )
        return WebConsultationResponse(
            status="ready",
            message="Consulta procesada.",
            result=result,
        )
