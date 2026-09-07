from __future__ import annotations

from app.domain.explanation_mode import ExplanationMode
from app.domain.legal_consultation_query_configuration import (
    LegalConsultationQueryConfiguration,
)
from app.domain.orchestration import HybridOrchestrationRequest
from app.domain.traceability import CanonicalExecutionResult
from app.web.schemas import WebConsultationRequest


class LegalConsultationQueryConfigurationError(ValueError):
    """Error controlado de coherencia de consulta/configuracion G.3."""


def build_legal_consultation_query_configuration(
    web_request: WebConsultationRequest,
    orchestration_request: HybridOrchestrationRequest,
    canonical: CanonicalExecutionResult,
) -> LegalConsultationQueryConfiguration:
    """Proyecta G.3 sin inferir ni reejecutar razonamiento juridico."""

    if web_request.query != orchestration_request.query:
        raise LegalConsultationQueryConfigurationError(
            "G.3 detecto consultas distintas entre web y orquestacion."
        )

    if web_request.fiscal_year != orchestration_request.query_fiscal_year:
        raise LegalConsultationQueryConfigurationError(
            "G.3 detecto ejercicios solicitados inconsistentes."
        )

    requested_mode = ExplanationMode(web_request.mode)
    if requested_mode is not orchestration_request.explanation_mode:
        raise LegalConsultationQueryConfigurationError(
            "G.3 detecto modos de explicacion inconsistentes."
        )

    trace = canonical.traceability

    return LegalConsultationQueryConfiguration(
        query=web_request.query,
        query_sha256=trace.query_sha256,
        query_date=orchestration_request.query_date,
        requested_fiscal_year=web_request.fiscal_year,
        resolved_fiscal_year=trace.query_fiscal_year,
        explanation_mode=orchestration_request.explanation_mode,
        top_k=orchestration_request.top_k,
        session_jurisprudence_attached=(
            web_request.jurisprudence_session_id is not None
        ),
    )
