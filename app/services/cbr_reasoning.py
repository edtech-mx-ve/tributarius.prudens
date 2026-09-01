from __future__ import annotations

from app.domain.cbr import (
    CaseStatus,
    CBRMatch,
    CBRReuseAssessment,
    CBRReuseDecision,
    CBRRevision,
)

MINIMUM_REUSE_SIMILARITY = 0.75


def assess_case_reuse(
    match: CBRMatch,
    *,
    current_normative_refs: set[str],
) -> CBRReuseAssessment:
    """Evalúa si un precedente experiencial puede reutilizarse como apoyo."""
    shared = sorted(set(match.normative_refs) & current_normative_refs)

    if match.status in {CaseStatus.SUPERSEDED, CaseStatus.INVALIDATED}:
        return CBRReuseAssessment(
            case_id=match.case_id,
            decision=CBRReuseDecision.REJECTED,
            shared_normative_refs=shared,
            reason="El caso no está habilitado para reutilización.",
            requires_human_review=True,
        )

    if match.similarity < MINIMUM_REUSE_SIMILARITY:
        return CBRReuseAssessment(
            case_id=match.case_id,
            decision=CBRReuseDecision.REJECTED,
            shared_normative_refs=shared,
            reason=(
                "La similitud del caso es insuficiente para reutilizarlo "
                "como experiencia fiscal."
            ),
            requires_human_review=True,
        )

    if match.status == CaseStatus.HISTORICAL:
        return CBRReuseAssessment(
            case_id=match.case_id,
            decision=CBRReuseDecision.REVIEW_REQUIRED,
            shared_normative_refs=shared,
            reason="El caso es histórico y requiere revisión de vigencia.",
            requires_human_review=True,
        )

    if match.requires_human_review:
        return CBRReuseAssessment(
            case_id=match.case_id,
            decision=CBRReuseDecision.REVIEW_REQUIRED,
            shared_normative_refs=shared,
            reason="La recuperación CBR marcó el caso para revisión humana.",
            requires_human_review=True,
        )

    if not match.normative_refs:
        return CBRReuseAssessment(
            case_id=match.case_id,
            decision=CBRReuseDecision.REVIEW_REQUIRED,
            shared_normative_refs=[],
            reason="El caso no tiene referencias normativas trazables.",
            requires_human_review=True,
        )

    if not shared:
        return CBRReuseAssessment(
            case_id=match.case_id,
            decision=CBRReuseDecision.REVIEW_REQUIRED,
            shared_normative_refs=[],
            reason="No hay referencia normativa compartida con el contexto vigente.",
            requires_human_review=True,
        )

    return CBRReuseAssessment(
        case_id=match.case_id,
        decision=CBRReuseDecision.ELIGIBLE,
        shared_normative_refs=shared,
        reason=(
            "Caso activo, suficientemente similar y compatible con las "
            "referencias normativas suministradas."
        ),
        requires_human_review=False,
    )


def revise_case_resolution(
    match: CBRMatch,
    *,
    revised_summary: str,
    reviewer_confirmed: bool,
    reuse_assessment: CBRReuseAssessment | None = None,
) -> CBRRevision:
    """Registra adaptación humana sin convertir CBR en autoridad normativa."""
    if not reviewer_confirmed:
        raise ValueError("La revisión de un caso requiere confirmación humana.")

    if reuse_assessment is not None:
        if reuse_assessment.case_id != match.case_id:
            raise ValueError(
                "La evaluación de reutilización no corresponde al caso revisado."
            )
        if reuse_assessment.decision == CBRReuseDecision.REJECTED:
            raise ValueError(
                "Un caso rechazado por el control CBR no puede adaptarse."
            )

    if match.status in {CaseStatus.SUPERSEDED, CaseStatus.INVALIDATED}:
        raise ValueError(
            "Un caso sustituido o invalidado no puede adaptarse."
        )

    if match.similarity < MINIMUM_REUSE_SIMILARITY:
        raise ValueError(
            "La similitud del caso es insuficiente para una adaptación controlada."
        )

    clean = revised_summary.strip()
    if not clean:
        raise ValueError("La revisión no puede quedar vacía.")

    if clean == match.resolution_summary.strip():
        raise ValueError(
            "La adaptación debe registrar un cambio explícito respecto del caso fuente."
        )

    return CBRRevision(
        source_case_id=match.case_id,
        revised_resolution_summary=clean,
        reviewer_confirmed=True,
    )
