from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.hybrid_integral_legal_analysis import HybridIntegralLegalAnalysis
from app.domain.hybrid_legal_decision import HybridLegalDecision
from app.domain.integral_legal_analysis import IntegralLegalAnalysis
from app.domain.legal_consultation_applied_rbs import (
    LegalConsultationAppliedRBS,
)
from app.domain.legal_consultation_query_configuration import (
    LegalConsultationQueryConfiguration,
)
from app.domain.legal_consultation_retrieved_cbr import (
    LegalConsultationRetrievedCBR,
)
from app.domain.legal_consultation_session_jurisprudence import (
    LegalConsultationSessionJurisprudence,
)
from app.domain.legal_decision import LegalDecision
from app.domain.legal_heuristics import LegalHeuristicEvaluation
from app.domain.traceability import TraceabilityRecord

LegalReportAnalyzer = HybridIntegralLegalAnalysis | IntegralLegalAnalysis
LegalReportDecision = HybridLegalDecision | LegalDecision


class LegalConsultationReport(BaseModel):
    """G.1: agrega resultados jurídicos ya calculados sin reejecutarlos."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    execution_id: str = Field(pattern=r"^TP-[A-F0-9]{32}$")
    folio: str = Field(pattern=r"^TP-\d{8}-[A-F0-9]{12}$")
    created_at_utc: datetime
    canonical_result_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    query_configuration: LegalConsultationQueryConfiguration
    applied_rbs: LegalConsultationAppliedRBS
    retrieved_cbr: LegalConsultationRetrievedCBR | None = None
    session_jurisprudence: LegalConsultationSessionJurisprudence = Field(
        default_factory=LegalConsultationSessionJurisprudence
    )
    heuristic_route: LegalHeuristicEvaluation | None = None
    analyzer: LegalReportAnalyzer
    legal_decision: LegalReportDecision
    traceability: TraceabilityRecord

    @model_validator(mode="after")
    def validate_report_boundaries(self) -> LegalConsultationReport:
        trace = self.traceability
        analysis = self.analyzer
        decision = self.legal_decision

        if self.execution_id != trace.execution_id:
            raise ValueError(
                "G.1 exige el mismo execution_id que la trazabilidad canónica."
            )

        if self.folio != trace.folio:
            raise ValueError(
                "G.1 exige el mismo folio que la trazabilidad canónica."
            )

        if self.created_at_utc != trace.created_at_utc:
            raise ValueError(
                "G.1 exige la misma fecha de la ejecución canónica."
            )

        if self.canonical_result_sha256 != trace.canonical_result_sha256:
            raise ValueError(
                "G.1 exige la huella del resultado canónico de origen."
            )

        if self.query_configuration.query_sha256 != trace.query_sha256:
            raise ValueError(
                "G.3 exige la misma consulta que la trazabilidad canonica."
            )

        if (
            self.query_configuration.resolved_fiscal_year
            != trace.query_fiscal_year
        ):
            raise ValueError(
                "G.3 exige el mismo ejercicio fiscal resuelto que la trazabilidad."
            )

        if (
            self.query_configuration.session_jurisprudence_attached
            != self.session_jurisprudence.user_attached
        ):
            raise ValueError(
                "G.7 exige coherencia entre adjunto jurisprudencial y reporte."
            )

        analysis_application = getattr(
            analysis,
            "jurisprudence_application",
            None,
        )
        decision_application = getattr(
            decision,
            "jurisprudence_application",
            None,
        )

        if analysis_application != decision_application:
            raise ValueError(
                "G.7 exige la misma aplicacion jurisprudencial en Analyzer y Legal Decision."
            )

        session_application = (
            self.session_jurisprudence.session_result.decision_application
            if self.session_jurisprudence.session_result is not None
            else None
        )

        if session_application != analysis_application:
            raise ValueError(
                "G.7 exige preservar exactamente la aplicacion E.6 de origen."
            )

        if (
            self.session_jurisprudence.binding_jurisprudence_applies
            and analysis_application is None
        ):
            raise ValueError(
                "G.7 no admite jurisprudencia vinculante sin proyeccion juridica."
            )

        if isinstance(analysis, HybridIntegralLegalAnalysis):
            if not isinstance(decision, HybridLegalDecision):
                raise ValueError(
                    "G.8 exige que Analyzer y Legal Decision pertenezcan "
                    "a la misma familia hibrida."
                )

            analyzer_projection = analysis.hybrid_projection
            decision_projection = decision.hybrid_projection

            if (
                analyzer_projection.verification_packet_sha256
                != decision_projection.source_verification_packet_sha256
            ):
                raise ValueError(
                    "G.8 detecto paquetes F.7 distintos entre Analyzer y Legal Decision."
                )

            if (
                analysis.canonical_conclusion
                != decision_projection.source_canonical_conclusion
            ):
                raise ValueError(
                    "G.8 detecto una conclusion fuente hibrida inconsistente."
                )

            if (
                analyzer_projection.applicable_normative_refs
                != decision_projection.applicable_normative_refs
            ):
                raise ValueError(
                    "G.8 exige la misma base normativa en F.8 y F.9."
                )

            if (
                analyzer_projection.reasoning_controller
                != decision_projection.reasoning_controller
            ):
                raise ValueError(
                    "G.8 exige preservar el mismo controlador de razonamiento."
                )

            if (
                analyzer_projection.legal_authority_source
                != decision_projection.legal_authority_source
            ):
                raise ValueError(
                    "G.8 exige preservar la misma autoridad juridica."
                )

            if (
                analyzer_projection.jurisprudence_effect
                != decision_projection.jurisprudence_effect
            ):
                raise ValueError(
                    "G.8 exige preservar el efecto jurisprudencial de F.8."
                )

            if (
                analyzer_projection.binding_interpretation_required
                != decision_projection.binding_interpretation_required
            ):
                raise ValueError(
                    "G.8 exige preservar la interpretacion vinculante."
                )

            if not decision_projection.single_determination_preserved:
                raise ValueError(
                    "G.8 exige preservar una sola determinacion juridica."
                )

            if decision_projection.second_conclusion_created:
                raise ValueError(
                    "G.8 no admite una segunda conclusion juridica."
                )

        elif isinstance(decision, HybridLegalDecision):
            raise ValueError(
                "G.8 exige que Analyzer y Legal Decision pertenezcan "
                "a la misma familia hibrida."
            )

        elif decision.controlling_source != analysis.controlling_source:
            raise ValueError(
                "G.8 exige preservar la fuente controladora de Analyzer 1.0."
            )

        if decision.source_analysis_schema_version != analysis.schema_version:
            raise ValueError(
                "G.1 detectó versiones incompatibles entre Analyzer y Legal Decision."
            )

        if decision.applicable_normative_refs != analysis.applicable_normative_refs:
            raise ValueError(
                "G.1 no permite alterar la base normativa entre Analyzer y Legal Decision."
            )

        if (
            decision.conclusion is not None
            and decision.conclusion != analysis.canonical_conclusion
        ):
            raise ValueError(
                "G.1 no permite crear una segunda conclusión jurídica."
            )

        if decision.requires_human_review != analysis.requires_human_review:
            raise ValueError(
                "G.1 debe preservar la revisión humana del resultado jurídico."
            )

        return self
