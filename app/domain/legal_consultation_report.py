from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.hybrid_integral_legal_analysis import HybridIntegralLegalAnalysis
from app.domain.hybrid_legal_decision import HybridLegalDecision
from app.domain.integral_legal_analysis import IntegralLegalAnalysis
from app.domain.legal_consultation_query_configuration import (
    LegalConsultationQueryConfiguration,
)
from app.domain.legal_decision import LegalDecision
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
