from __future__ import annotations

from app.domain.legal_hypothesis import (
    ControlledLegalHypothesis,
    ControlledLegalHypothesisResult,
    LegalHypothesisStatus,
)


class LegalHypothesisValidationError(ValueError):
    """La hipótesis LLM violó la frontera jurídica autorizada."""


def validate_controlled_legal_hypothesis(
    hypothesis: ControlledLegalHypothesis,
    *,
    authorized_evidence_ids: list[str],
) -> ControlledLegalHypothesisResult:
    """Valida una hipótesis sin convertirla en conclusión jurídica.

    La hipótesis solo orienta la investigación posterior. No puede modificar
    resultados deterministas, introducir autoridad externa ni citar evidencia
    fuera de la frontera autorizada.
    """
    allowed = set(authorized_evidence_ids)
    invalid_ids = [
        evidence_id
        for evidence_id in hypothesis.evidence_ids
        if evidence_id not in allowed
    ]
    if invalid_ids:
        raise LegalHypothesisValidationError(
            "La hipótesis intentó citar evidencia fuera del contexto autorizado."
        )

    if hypothesis.changes_deterministic_result:
        raise LegalHypothesisValidationError(
            "La hipótesis LLM no puede modificar resultados jurídicos deterministas."
        )

    if hypothesis.asserts_external_legal_authority:
        raise LegalHypothesisValidationError(
            "La hipótesis LLM no puede introducir autoridad jurídica externa."
        )

    if not hypothesis.requires_validation:
        raise LegalHypothesisValidationError(
            "Toda hipótesis jurídica generativa debe quedar sujeta a validación."
        )

    if hypothesis.status != LegalHypothesisStatus.PROPOSED:
        raise LegalHypothesisValidationError(
            "Una hipótesis aceptada por la frontera debe conservar estado proposed."
        )

    return ControlledLegalHypothesisResult(
        generation_performed=True,
        hypothesis=hypothesis.model_copy(deep=True),
        authorized_evidence_ids=list(dict.fromkeys(authorized_evidence_ids)),
        requires_human_review=bool(hypothesis.uncertainties),
        trace=[
            "legal_hypothesis:controlled=true",
            "legal_hypothesis:status=proposed",
            "legal_hypothesis:requires_validation=true",
            "legal_hypothesis:deterministic_result_unchanged=true",
        ],
    )
