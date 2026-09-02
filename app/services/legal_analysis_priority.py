from __future__ import annotations

from app.domain.hybrid_coordination import HybridCoordinationResult
from app.domain.legal_heuristics import LegalHeuristicSignal

_PRIORITY_BY_CODE: dict[str, int] = {
    "HEUR-NORM-001": 10,
    "HEUR-TEMP-003": 20,
    "HEUR-TEMP-001": 30,
    "HEUR-TEMP-002": 40,
    "HEUR-EVID-002": 50,
    "HEUR-EVID-001": 60,
    "HEUR-EVID-004": 70,
    "HEUR-REVIEW-001": 80,
    "HEUR-EVID-003": 90,
    "HEUR-PRIORITY-001": 100,
    "HEUR-NORM-OK": 900,
}

_DIRECTIVE_BY_CODE: dict[str, str] = {
    "HEUR-NORM-001": "Verificar fundamento normativo de la conclusión RBS.",
    "HEUR-TEMP-003": "Excluir el precedente temporalmente inhabilitado del apoyo CBR.",
    "HEUR-TEMP-001": "Resolver vigencia y compatibilidad temporal de las fuentes.",
    "HEUR-TEMP-002": "Verificar vigencia normativa del precedente histórico.",
    "HEUR-EVID-002": "Depurar los hechos conflictivos que afectan al RBS.",
    "HEUR-EVID-001": "Completar o depurar evidencia antes del cierre jurídico.",
    "HEUR-EVID-004": "Resolver la incertidumbre del precedente CBR antes de reutilizarlo.",
    "HEUR-REVIEW-001": "Someter la decisión híbrida a revisión humana.",
    "HEUR-EVID-003": "Verificar diferencias fácticas antes de reutilizar el caso CBR.",
    "HEUR-PRIORITY-001": "Priorizar norma aplicable sobre analogía experiencial.",
}


def build_legal_analysis_priority(
    coordination: HybridCoordinationResult,
    signals: list[LegalHeuristicSignal],
    existing_priority: list[str] | None = None,
) -> list[str]:
    """Ordena acciones jurídicas pendientes sin alterar la decisión híbrida.

    La fuente controladora y la prioridad normativa son invariantes del resultado,
    no tareas pendientes. Por ello no se insertan artificialmente como primer
    elemento de ``analysis_priority``. La lista conserva el significado histórico:
    qué debe atenderse primero para cerrar jurídicamente el análisis.
    """
    del coordination  # El contrato se conserva para futuras reglas contextuales.

    directives: list[tuple[int, int, str]] = []
    seen: set[str] = set()

    for index, signal in enumerate(signals):
        directive = _DIRECTIVE_BY_CODE.get(signal.code)
        if directive is None or directive in seen:
            continue
        seen.add(directive)
        directives.append(
            (_PRIORITY_BY_CODE.get(signal.code, 500), index, directive)
        )

    for index, directive in enumerate(existing_priority or []):
        if directive in seen:
            continue
        seen.add(directive)
        directives.append((700, index, directive))

    directives.sort(key=lambda item: (item[0], item[1], item[2]))
    return [directive for _, _, directive in directives]
