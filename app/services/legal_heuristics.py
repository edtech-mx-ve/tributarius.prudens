from __future__ import annotations

from app.domain.hybrid_coordination import (
    HybridCoordinationResult,
    HybridReasoningRelation,
)
from app.domain.legal_heuristics import (
    LegalHeuristicEvaluation,
    LegalHeuristicKind,
    LegalHeuristicLevel,
    LegalHeuristicSignal,
)
from app.services.legal_analysis_priority import build_legal_analysis_priority
from app.services.legal_evidentiary_temporal_heuristics import (
    evaluate_evidentiary_temporal_signals,
)


def _signal(
    *,
    code: str,
    kind: LegalHeuristicKind,
    level: LegalHeuristicLevel,
    message: str,
    evidence_refs: list[str] | None = None,
    requires_review: bool = False,
) -> LegalHeuristicSignal:
    return LegalHeuristicSignal(
        code=code,
        kind=kind,
        level=level,
        message=message,
        evidence_refs=evidence_refs or [],
        requires_review=requires_review,
    )


def evaluate_legal_heuristics(
    coordination: HybridCoordinationResult,
) -> LegalHeuristicEvaluation:
    """Evalúa señales jurídicas explícitas sin recalcular la decisión híbrida.

    Las heurísticas únicamente priorizan análisis, advierten insuficiencia o
    conflicto y propagan revisión. Nunca cambian la conclusión canónica ni la
    fuente controladora decididas por la coordinación RBS-CBR.
    """
    signals: list[LegalHeuristicSignal] = []
    priority: list[str] = []

    rbs = coordination.rbs_result
    cbr = coordination.cbr_result

    if not rbs.legal_basis:
        signals.append(
            _signal(
                code="HEUR-NORM-001",
                kind=LegalHeuristicKind.NORMATIVE_RELEVANCE,
                level=LegalHeuristicLevel.REVIEW,
                message=(
                    "La conclusión controladora no expone fundamento normativo "
                    "suficiente para sustentar su relevancia jurídica."
                ),
                requires_review=True,
            )
        )
        priority.append("Verificar fundamento normativo de la conclusión RBS.")
    else:
        signals.append(
            _signal(
                code="HEUR-NORM-OK",
                kind=LegalHeuristicKind.NORMATIVE_RELEVANCE,
                level=LegalHeuristicLevel.INFO,
                message="La conclusión RBS expone fundamento jurídico identificable.",
                evidence_refs=list(rbs.legal_basis),
            )
        )

    insufficient = (
        rbs.conclusion is None
        or coordination.relation == HybridReasoningRelation.INSUFFICIENT_EVIDENCE
        or bool(rbs.uncertainty)
    )
    if insufficient:
        signals.append(
            _signal(
                code="HEUR-EVID-001",
                kind=LegalHeuristicKind.EVIDENCE_SUFFICIENCY,
                level=LegalHeuristicLevel.REVIEW,
                message=(
                    "La evidencia disponible presenta insuficiencia o incertidumbre "
                    "que limita el cierre automático del análisis."
                ),
                evidence_refs=[*rbs.references, *cbr.references],
                requires_review=True,
            )
        )
        priority.append("Completar o depurar evidencia antes del cierre jurídico.")

    evidentiary_temporal_signals, evidentiary_temporal_priority = (
        evaluate_evidentiary_temporal_signals(coordination)
    )
    signals.extend(evidentiary_temporal_signals)
    priority.extend(evidentiary_temporal_priority)

    relation_requires_review = coordination.relation in {
        HybridReasoningRelation.CONTRADICTION,
        HybridReasoningRelation.EXCEPTION,
        HybridReasoningRelation.HUMAN_REVIEW,
    }
    if coordination.requires_review or relation_requires_review:
        signals.append(
            _signal(
                code="HEUR-REVIEW-001",
                kind=LegalHeuristicKind.HUMAN_REVIEW,
                level=LegalHeuristicLevel.REVIEW,
                message=(
                    "La coordinación híbrida contiene una condición que exige "
                    "revisión humana antes de considerar cerrado el análisis."
                ),
                evidence_refs=list(coordination.shared_legal_basis),
                requires_review=True,
            )
        )
        priority.append("Someter la decisión híbrida a revisión humana.")

    if coordination.relation == HybridReasoningRelation.CORRECTION:
        signals.append(
            _signal(
                code="HEUR-PRIORITY-001",
                kind=LegalHeuristicKind.ANALYSIS_PRIORITY,
                level=LegalHeuristicLevel.WARNING,
                message=(
                    "El precedente CBR no comparte fundamento suficiente con RBS; "
                    "debe priorizarse el análisis normativo antes que la analogía."
                ),
                evidence_refs=list(rbs.legal_basis),
            )
        )
        priority.append("Priorizar norma aplicable sobre analogía experiencial.")

    priority = build_legal_analysis_priority(
        coordination,
        signals,
        priority,
    )

    review = coordination.requires_review or any(
        signal.requires_review for signal in signals
    )

    return LegalHeuristicEvaluation(
        canonical_conclusion=coordination.conclusion,
        controlling_source=coordination.controlling_source,
        signals=signals,
        analysis_priority=priority,
        requires_review=review,
        normative_priority_preserved=(
            coordination.factors.normative_priority_preserved
            and coordination.controlling_source in {None, "rbs"}
        ),
        trace=[
            "heuristics:explicit=true",
            f"heuristics:signals={len(signals)}",
            f"heuristics:priority_items={len(priority)}",
            f"heuristics:requires_review={str(review).lower()}",
            "heuristics:canonical_conclusion_unchanged=true",
        ],
    )
