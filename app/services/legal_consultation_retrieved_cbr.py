from __future__ import annotations

from app.domain.legal_consultation_retrieved_cbr import (
    LegalConsultationRetrievedCBR,
)
from app.domain.orchestration import HybridOrchestrationResult
from app.domain.traceability import CanonicalExecutionResult


class LegalConsultationRetrievedCBRError(ValueError):
    """Error de integridad del CBR recuperado G.6."""


def build_legal_consultation_retrieved_cbr(
    result: HybridOrchestrationResult,
    canonical: CanonicalExecutionResult,
) -> LegalConsultationRetrievedCBR | None:
    """Proyecta CBR ya ejecutado sin recuperar ni normalizar de nuevo."""

    retrieval = result.cbr_result
    assessments = result.cbr_reuse_assessments
    normalized = result.cbr_reasoning

    if retrieval is None and not assessments and normalized is None:
        return None

    expected_cbr = {
        "retrieval": (
            retrieval.model_dump(mode="json")
            if retrieval is not None
            else None
        ),
        "reuse_assessments": [
            item.model_dump(mode="json")
            for item in assessments
        ],
    }

    if canonical.cbr != expected_cbr:
        raise LegalConsultationRetrievedCBRError(
            "G.6 detecto divergencia en el CBR canonico recuperado."
        )

    if normalized is None:
        raise LegalConsultationRetrievedCBRError(
            "G.6 detecto CBR recuperado sin razonamiento normalizado."
        )

    normalized_payload = normalized.model_dump(mode="json")

    if canonical.cbr_reasoning is None:
        raise LegalConsultationRetrievedCBRError(
            "G.6 detecto perdida del razonamiento CBR canonico."
        )

    if canonical.cbr_reasoning != normalized_payload:
        raise LegalConsultationRetrievedCBRError(
            "G.6 detecto divergencia en el razonamiento CBR canonico."
        )

    controlling_source = None
    if result.hybrid_coordination is not None:
        controlling_source = result.hybrid_coordination.controlling_source
        if controlling_source not in {None, "rbs"}:
            raise LegalConsultationRetrievedCBRError(
                "G.6 no permite que CBR controle la decision juridica."
            )

    return LegalConsultationRetrievedCBR(
        retrieval=(
            retrieval.model_copy(deep=True)
            if retrieval is not None
            else None
        ),
        reuse_assessments=[
            item.model_copy(deep=True)
            for item in assessments
        ],
        normalized_reasoning=normalized.model_copy(deep=True),
        hybrid_controlling_source=(
            "rbs" if controlling_source == "rbs" else None
        ),
    )
