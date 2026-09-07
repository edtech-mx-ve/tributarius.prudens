from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.hybrid_integral_legal_analysis import HybridIntegralLegalAnalysis
from app.domain.hybrid_legal_decision import HybridLegalDecision
from app.domain.integral_legal_analysis import IntegralLegalAnalysis
from app.domain.legal_decision import LegalDecision
from app.domain.traceability import TraceabilityRecord

LegalReportAnalyzer = HybridIntegralLegalAnalysis | IntegralLegalAnalysis
LegalReportDecision = HybridLegalDecision | LegalDecision


class LegalConsultationReport(BaseModel):
    """G.1: agrega resultados jur?dicos ya calculados sin reejecutarlos."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    execution_id: str = Field(pattern=r"^TP-[A-F0-9]{32}$")
    folio: str = Field(pattern=r"^TP-\d{8}-[A-F0-9]{12}$")
    created_at_utc: datetime
    canonical_result_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
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
                "G.1 exige el mismo execution_id que la trazabilidad can?nica."
            )

        if self.folio != trace.folio:
            raise ValueError(
                "G.1 exige el mismo folio que la trazabilidad can?nica."
            )

        if self.created_at_utc != trace.created_at_utc:
            raise ValueError(
                "G.1 exige la misma fecha de la ejecuci?n can?nica."
            )

        if self.canonical_result_sha256 != trace.canonical_result_sha256:
            raise ValueError(
                "G.1 exige la huella del resultado can?nico de origen."
            )

        if decision.source_analysis_schema_version != analysis.schema_version:
            raise ValueError(
                "G.1 detect? versiones incompatibles entre Analyzer y Legal Decision."
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
                "G.1 no permite crear una segunda conclusi?n jur?dica."
            )

        if decision.requires_human_review != analysis.requires_human_review:
            raise ValueError(
                "G.1 debe preservar la revisi?n humana del resultado jur?dico."
            )

        return self
