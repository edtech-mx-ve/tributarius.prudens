from __future__ import annotations

from app.domain.hybrid_coordination import HybridCoordinationResult
from app.domain.legal_heuristics import (
    LegalHeuristicKind,
    LegalHeuristicLevel,
    LegalHeuristicSignal,
)

_INELIGIBLE_TEMPORAL_CONTEXTS = frozenset({"superseded", "invalidated"})


def evaluate_evidentiary_temporal_signals(
    coordination: HybridCoordinationResult,
) -> tuple[list[LegalHeuristicSignal], list[str]]:
    """Evalúa suficiencia probatoria y temporalidad sin alterar la decisión híbrida."""
    signals: list[LegalHeuristicSignal] = []
    priority: list[str] = []

    rbs = coordination.rbs_result
    cbr = coordination.cbr_result

    if rbs.conflicting_facts:
        signals.append(
            LegalHeuristicSignal(
                code="HEUR-EVID-002",
                kind=LegalHeuristicKind.EVIDENCE_SUFFICIENCY,
                level=LegalHeuristicLevel.REVIEW,
                message=(
                    "El RBS conserva hechos en conflicto; la conclusión normativa "
                    "requiere depuración probatoria antes del cierre."
                ),
                evidence_refs=list(rbs.conflicting_facts),
                requires_review=True,
            )
        )
        priority.append("Depurar los hechos conflictivos que afectan al RBS.")

    if cbr.conflicting_facts and cbr.applicability is True:
        signals.append(
            LegalHeuristicSignal(
                code="HEUR-EVID-003",
                kind=LegalHeuristicKind.EVIDENCE_SUFFICIENCY,
                level=LegalHeuristicLevel.WARNING,
                message=(
                    "El caso CBR reutilizable presenta diferencias fácticas frente "
                    "a la consulta actual; la analogía debe limitarse a los hechos "
                    "materialmente coincidentes."
                ),
                evidence_refs=list(cbr.conflicting_facts),
            )
        )
        priority.append("Verificar diferencias fácticas antes de reutilizar el caso CBR.")

    if cbr.uncertainty and cbr.applicability is not False:
        signals.append(
            LegalHeuristicSignal(
                code="HEUR-EVID-004",
                kind=LegalHeuristicKind.EVIDENCE_SUFFICIENCY,
                level=LegalHeuristicLevel.REVIEW,
                message=(
                    "El componente CBR conserva incertidumbre relevante para su "
                    "reutilización como apoyo experiencial."
                ),
                evidence_refs=list(cbr.uncertainty),
                requires_review=True,
            )
        )
        priority.append("Resolver la incertidumbre del precedente CBR antes de reutilizarlo.")

    temporal_context = (cbr.temporal_context or "").strip().casefold()
    if temporal_context == "historical":
        signals.append(
            LegalHeuristicSignal(
                code="HEUR-TEMP-002",
                kind=LegalHeuristicKind.TEMPORAL_CONFLICT,
                level=LegalHeuristicLevel.REVIEW,
                message=(
                    "El precedente CBR es histórico; su reutilización exige verificar "
                    "vigencia y continuidad del fundamento normativo."
                ),
                evidence_refs=[cbr.temporal_context or "historical"],
                requires_review=True,
            )
        )
        priority.append("Verificar vigencia normativa del precedente histórico.")

    if temporal_context in _INELIGIBLE_TEMPORAL_CONTEXTS:
        signals.append(
            LegalHeuristicSignal(
                code="HEUR-TEMP-003",
                kind=LegalHeuristicKind.TEMPORAL_CONFLICT,
                level=LegalHeuristicLevel.REVIEW,
                message=(
                    "El precedente CBR está sustituido o invalidado y no debe "
                    "utilizarse como apoyo para cerrar el análisis actual."
                ),
                evidence_refs=[cbr.temporal_context or temporal_context],
                requires_review=True,
            )
        )
        priority.append("Excluir el precedente temporalmente inhabilitado del apoyo CBR.")

    if (
        rbs.temporal_context
        and cbr.temporal_context
        and rbs.temporal_context != cbr.temporal_context
        and cbr.applicability is True
    ):
        signals.append(
            LegalHeuristicSignal(
                code="HEUR-TEMP-001",
                kind=LegalHeuristicKind.TEMPORAL_CONFLICT,
                level=LegalHeuristicLevel.REVIEW,
                message=(
                    "RBS y CBR operan con contextos temporales distintos; debe "
                    "verificarse la vigencia aplicable antes de reutilizar el caso."
                ),
                evidence_refs=[rbs.temporal_context, cbr.temporal_context],
                requires_review=True,
            )
        )
        priority.append("Resolver vigencia y compatibilidad temporal de las fuentes.")

    return signals, list(dict.fromkeys(priority))
