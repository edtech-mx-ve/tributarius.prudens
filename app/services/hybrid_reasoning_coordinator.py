from __future__ import annotations

import re
import unicodedata

from app.domain.hybrid_coordination import (
    HybridCoordinationContext,
    HybridCoordinationFactors,
    HybridCoordinationResult,
    HybridReasoningRelation,
)
from app.domain.hybrid_reasoning import NormalizedReasoningResult, ReasoningSource


def _fold(text: str | None) -> str:
    if not text:
        return ""
    folded = unicodedata.normalize("NFKD", text.casefold())
    ascii_text = "".join(char for char in folded if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", ascii_text))


def _shared_basis(
    rbs: NormalizedReasoningResult,
    cbr: NormalizedReasoningResult,
) -> list[str]:
    cbr_refs = set(cbr.legal_basis)
    return [ref for ref in rbs.legal_basis if ref in cbr_refs]


def _trace(
    relation: HybridReasoningRelation,
    rbs: NormalizedReasoningResult,
    cbr: NormalizedReasoningResult,
) -> list[str]:
    return [
        f"coordination:relation={relation.value}",
        *[f"rbs:{item}" for item in rbs.trace],
        *[f"cbr:{item}" for item in cbr.trace],
    ]


def coordinate_rbs_cbr(
    rbs: NormalizedReasoningResult,
    cbr: NormalizedReasoningResult,
    *,
    context: HybridCoordinationContext | None = None,
) -> HybridCoordinationResult:
    """Contrasta RBS y CBR sin otorgar autoridad normativa a la experiencia.

    La salida RBS controla cuando existe una conclusión explícita. CBR puede
    confirmar, revelar conflicto o aportar una excepción previamente sustentada,
    pero nunca desplaza por sí solo una regla/norma vigente.
    """
    if rbs.reasoning_source != ReasoningSource.RBS:
        raise ValueError("El primer resultado debe proceder del RBS.")
    if cbr.reasoning_source != ReasoningSource.CBR:
        raise ValueError("El segundo resultado debe proceder del CBR.")

    context = context or HybridCoordinationContext()
    shared = _shared_basis(rbs, cbr)
    controlling = ReasoningSource.RBS.value if rbs.conclusion else None
    canonical = rbs.conclusion
    factors = HybridCoordinationFactors(
        rbs_has_conclusion=rbs.conclusion is not None,
        rbs_applicability=rbs.applicability,
        cbr_applicability=cbr.applicability,
        cbr_similarity=cbr.confidence,
        cbr_temporal_context=cbr.temporal_context,
        shared_legal_basis_count=len(shared),
        rbs_requires_review=rbs.requires_review,
        cbr_requires_review=cbr.requires_review,
        normative_priority_preserved=(
            controlling in {None, ReasoningSource.RBS.value}
        ),
    )

    if rbs.requires_review or cbr.requires_review:
        relation = HybridReasoningRelation.HUMAN_REVIEW
        reasons = [
            "Al menos una fuente de razonamiento exige revisión humana antes de coordinar."
        ]
        review = True
    elif rbs.conclusion is None:
        relation = HybridReasoningRelation.INSUFFICIENT_EVIDENCE
        reasons = ["El RBS no produjo una conclusión determinista que pueda controlar."]
        review = True
    elif cbr.conclusion is None or cbr.applicability is not True:
        relation = HybridReasoningRelation.INSUFFICIENT_EVIDENCE
        reasons = [
            "No existe experiencia CBR aplicable suficiente para contrastar la conclusión RBS."
        ]
        review = False
    elif context.exception_supported:
        relation = HybridReasoningRelation.EXCEPTION
        reasons = [
            "Existe una excepción expresamente sustentada que debe "
            "contrastarse con la regla general."
        ]
        if context.exception_basis:
            reasons.append(
                "Fundamento de excepción: " + ", ".join(context.exception_basis) + "."
            )
        review = True
    elif not shared:
        relation = HybridReasoningRelation.CORRECTION
        reasons = [
            "El caso CBR no comparte fundamento jurídico con la conclusión RBS "
            "y no puede reutilizarse para desplazarla."
        ]
        review = False
    elif _fold(rbs.conclusion) == _fold(cbr.conclusion):
        relation = HybridReasoningRelation.CONFIRMATION
        reasons = [
            "RBS y CBR alcanzan la misma conclusión y comparten fundamento jurídico."
        ]
        review = False
    else:
        relation = HybridReasoningRelation.CONTRADICTION
        reasons = [
            "RBS y CBR difieren pese a compartir fundamento jurídico; "
            "prevalece provisionalmente la conclusión RBS y se requiere revisión."
        ]
        review = True

    return HybridCoordinationResult(
        relation=relation,
        conclusion=canonical,
        controlling_source=controlling,
        rbs_result=rbs,
        cbr_result=cbr,
        factors=factors,
        shared_legal_basis=shared,
        reasons=reasons,
        requires_review=review,
        trace=_trace(relation, rbs, cbr),
    )
