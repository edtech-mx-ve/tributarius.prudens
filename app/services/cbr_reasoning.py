from __future__ import annotations

from app.domain.cbr import (
    CaseStatus,
    CBRMatch,
    CBRReuseAssessment,
    CBRReuseDecision,
    CBRRevision,
)


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

    if match.status == CaseStatus.HISTORICAL:
        return CBRReuseAssessment(
            case_id=match.case_id,
            decision=CBRReuseDecision.REVIEW_REQUIRED,
            shared_normative_refs=shared,
            reason="El caso es histórico y requiere revisión de vigencia.",
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
        reason="Caso activo y compatible con las referencias normativas suministradas.",
        requires_human_review=False,
    )


def revise_case_resolution(
    match: CBRMatch,
    *,
    revised_summary: str,
    reviewer_confirmed: bool,
) -> CBRRevision:
    """Registra una revisión; nunca confirma cambios automáticamente."""
    if not reviewer_confirmed:
        raise ValueError("La revisión de un caso requiere confirmación humana.")
    clean = revised_summary.strip()
    if not clean:
        raise ValueError("La revisión no puede quedar vacía.")
    return CBRRevision(
        source_case_id=match.case_id,
        revised_resolution_summary=clean,
        reviewer_confirmed=True,
    )
