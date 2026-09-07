from __future__ import annotations

from app.domain.hybrid_integral_legal_analysis import (
    HybridIntegralLegalAnalysis,
)
from app.domain.hybrid_legal_decision import HybridLegalDecision
from app.domain.integral_legal_analysis import IntegralLegalAnalysis
from app.domain.legal_consultation_report import LegalConsultationReport
from app.domain.legal_decision import LegalDecision
from app.domain.orchestration import (
    HybridOrchestrationRequest,
    HybridOrchestrationResult,
)
from app.domain.traceability import CanonicalExecutionResult
from app.services.legal_consultation_applied_rbs import (
    build_legal_consultation_applied_rbs,
)
from app.services.legal_consultation_heuristic_route import (
    build_legal_consultation_heuristic_route,
)
from app.services.legal_consultation_mode_explanation import (
    build_legal_consultation_mode_explanation,
)
from app.services.legal_consultation_query_configuration import (
    build_legal_consultation_query_configuration,
)
from app.services.legal_consultation_retrieved_cbr import (
    build_legal_consultation_retrieved_cbr,
)
from app.services.legal_consultation_session_jurisprudence import (
    build_legal_consultation_session_jurisprudence,
)
from app.services.traceability import verify_canonical_integrity
from app.web.schemas import WebConsultationRequest

LegalReportAnalyzer = HybridIntegralLegalAnalysis | IntegralLegalAnalysis
LegalReportDecision = HybridLegalDecision | LegalDecision


class LegalConsultationReportBuildError(ValueError):
    """G.12: fallo controlado al ensamblar el reporte ya calculado."""


def build_legal_consultation_report(
    *,
    web_request: WebConsultationRequest,
    orchestration_request: HybridOrchestrationRequest,
    result: HybridOrchestrationResult,
    canonical: CanonicalExecutionResult,
    analyzer: LegalReportAnalyzer,
    legal_decision: LegalReportDecision,
) -> LegalConsultationReport:
    """Ensambla G.1-G.9 sin reejecutar razonamiento juridico."""

    if not verify_canonical_integrity(canonical):
        raise LegalConsultationReportBuildError(
            "G.12 exige una ejecucion canonica integra."
        )

    query_configuration = (
        build_legal_consultation_query_configuration(
            web_request,
            orchestration_request,
            canonical,
        )
    )

    mode_explanation = (
        build_legal_consultation_mode_explanation(
            canonical,
            query_configuration,
        )
    )

    applied_rbs = build_legal_consultation_applied_rbs(
        result,
        canonical,
    )

    retrieved_cbr = build_legal_consultation_retrieved_cbr(
        result,
        canonical,
    )

    jurisprudence = (
        build_legal_consultation_session_jurisprudence(
            orchestration_request,
            result,
            canonical,
        )
    )

    heuristic_route = (
        build_legal_consultation_heuristic_route(
            result,
            canonical,
        )
    )

    trace = canonical.traceability

    if trace.canonical_result_sha256 is None:
        raise LegalConsultationReportBuildError(
            "G.12 exige SHA-256 canonico."
        )

    return LegalConsultationReport(
        execution_id=canonical.execution_id,
        folio=canonical.folio,
        created_at_utc=canonical.created_at_utc,
        canonical_result_sha256=(
            trace.canonical_result_sha256
        ),
        query_configuration=query_configuration,
        mode_explanation=mode_explanation,
        applied_rbs=applied_rbs,
        retrieved_cbr=retrieved_cbr,
        session_jurisprudence=jurisprudence,
        heuristic_route=heuristic_route,
        analyzer=analyzer,
        legal_decision=legal_decision,
        traceability=trace,
    )
