from __future__ import annotations

from app.domain.legal_consultation_session_jurisprudence import (
    LegalConsultationSessionJurisprudence,
)
from app.domain.orchestration import (
    HybridOrchestrationRequest,
    HybridOrchestrationResult,
)
from app.domain.traceability import CanonicalExecutionResult


class LegalConsultationSessionJurisprudenceError(ValueError):
    """Error de integridad de jurisprudencia de sesion G.7."""


def build_legal_consultation_session_jurisprudence(
    request: HybridOrchestrationRequest,
    result: HybridOrchestrationResult,
    canonical: CanonicalExecutionResult,
) -> LegalConsultationSessionJurisprudence:
    """Proyecta solo jurisprudencia adjunta; no busca ni reevalua fuentes."""

    if result.jurisprudence_result is not None or canonical.jurisprudence is not None:
        raise LegalConsultationSessionJurisprudenceError(
            "G.7 no admite jurisprudencia ajena a la sesion del usuario."
        )

    attached = bool(request.session_jurisprudence_documents)
    session = result.session_jurisprudence_result

    ratio_payload = {
        document_id: record.model_dump(mode="json")
        for document_id, record in sorted(
            request.session_jurisprudence_ratio_records.items()
        )
    }

    if not attached and ratio_payload:
        raise LegalConsultationSessionJurisprudenceError(
            "G.7 detecto ratios jurisprudenciales sin documento adjunto."
        )

    canonical_ratios = canonical.session_jurisprudence_ratios
    if ratio_payload:
        if canonical_ratios != ratio_payload:
            raise LegalConsultationSessionJurisprudenceError(
                "G.7 detecto divergencia en las ratios jurisprudenciales canonicas."
            )
    elif canonical_ratios is not None:
        raise LegalConsultationSessionJurisprudenceError(
            "G.7 detecto ratios canonicas sin fuente de sesion."
        )

    expected_session = (
        session.model_dump(mode="json")
        if session is not None
        else None
    )

    if canonical.session_jurisprudence != expected_session:
        raise LegalConsultationSessionJurisprudenceError(
            "G.7 detecto divergencia en la jurisprudencia canonica de sesion."
        )

    if not attached:
        if session is not None:
            raise LegalConsultationSessionJurisprudenceError(
                "G.7 detecto jurisprudencia procesada sin adjunto del usuario."
            )
        return LegalConsultationSessionJurisprudence()

    ratios = [
        item.model_copy(deep=True)
        for _, item in sorted(
            request.session_jurisprudence_ratio_records.items()
        )
    ]

    if session is None:
        return LegalConsultationSessionJurisprudence(
            user_attached=True,
            ratio_records=ratios,
        )

    application = session.decision_application
    applicable_document_ids = (
        list(application.applicable_document_ids)
        if application is not None
        else []
    )
    binding_evidence_refs = (
        list(application.binding_evidence_refs)
        if application is not None
        else []
    )
    binding = bool(applicable_document_ids)

    return LegalConsultationSessionJurisprudence(
        user_attached=True,
        session_result=session.model_copy(deep=True),
        ratio_records=ratios,
        applicable_document_ids=applicable_document_ids,
        binding_evidence_refs=binding_evidence_refs,
        binding_jurisprudence_applies=binding,
        governing_interpretation=binding,
    )
