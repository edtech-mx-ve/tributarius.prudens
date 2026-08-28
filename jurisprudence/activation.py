from __future__ import annotations

from app.domain.jurisprudence import (
    JurisprudenceActivationDecision,
    JurisprudenceActivationReason,
)
from app.domain.query import QueryAnalysis, QueryIntent


def decide_jurisprudence_activation(
    analysis: QueryAnalysis,
    *,
    has_applicable_norms: bool,
) -> JurisprudenceActivationDecision:
    """Decide si se consulta jurisprudencia; no decide el fondo jurídico."""

    if analysis.jurisprudence_requested or (
        analysis.primary_intent == QueryIntent.RELATED_JURISPRUDENCE
    ):
        return JurisprudenceActivationDecision(
            activated=True,
            reason=JurisprudenceActivationReason.EXPLICIT_REQUEST,
            requires_human_review=False,
            detail="La persona usuaria solicitó jurisprudencia explícitamente.",
        )

    if analysis.ambiguities and has_applicable_norms:
        return JurisprudenceActivationDecision(
            activated=True,
            reason=JurisprudenceActivationReason.AMBIGUITY,
            requires_human_review=True,
            detail="Existe ambigüedad y una norma aplicable que puede requerir interpretación.",
        )

    if analysis.primary_intent == QueryIntent.INTERPRET_PROVISION and has_applicable_norms:
        return JurisprudenceActivationDecision(
            activated=True,
            reason=JurisprudenceActivationReason.INTERPRETATION_NEEDED,
            requires_human_review=True,
            detail="La consulta requiere interpretar una disposición identificada.",
        )

    if analysis.primary_intent == QueryIntent.ANALYZE_AUTHORITY_ACT:
        return JurisprudenceActivationDecision(
            activated=True,
            reason=JurisprudenceActivationReason.AUTHORITY_ACT,
            requires_human_review=True,
            detail="El análisis de un acto de autoridad puede requerir criterios jurisdiccionales.",
        )

    if analysis.primary_intent == QueryIntent.DEFENSE_OPTIONS:
        return JurisprudenceActivationDecision(
            activated=True,
            reason=JurisprudenceActivationReason.DEFENSE_ANALYSIS,
            requires_human_review=True,
            detail="El apoyo a defensa puede requerir criterios jurisdiccionales relevantes.",
        )

    return JurisprudenceActivationDecision(
        activated=False,
        reason=JurisprudenceActivationReason.NOT_NEEDED,
        requires_human_review=False,
        detail="La consulta puede continuar sin activar jurisprudencia.",
    )
