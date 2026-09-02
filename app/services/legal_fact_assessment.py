from __future__ import annotations

from app.domain.integral_legal_analysis import IntegralLegalAnalysis
from app.domain.legal_fact_assessment import (
    LegalFactAssessment,
    LegalFactMateriality,
    LegalFactStatus,
)
from app.domain.query import FactOrigin


def assess_legal_facts(
    analysis: IntegralLegalAnalysis,
) -> list[LegalFactAssessment]:
    """Valora hechos sin atribuir acreditación que Analyzer 1.0 no haya establecido."""

    assessments: list[LegalFactAssessment] = []

    for fact in analysis.facts:
        if fact.origin == FactOrigin.INFERRED:
            status = LegalFactStatus.INFERRED
            basis = (
                "Hecho inferido durante el análisis de la consulta; "
                "no equivale a un hecho acreditado."
            )
        else:
            status = LegalFactStatus.SUPPLIED
            basis = (
                "Hecho aportado expresamente en la consulta; "
                "su sola manifestación no acredita su veracidad."
            )

        assessments.append(
            LegalFactAssessment(
                name=fact.name,
                value=fact.value,
                origin=fact.origin,
                status=status,
                materiality=LegalFactMateriality.UNDETERMINED,
                basis=basis,
            )
        )

    existing_names = {item.name.casefold() for item in assessments}
    for missing in analysis.missing_fields:
        if missing.name.casefold() in existing_names:
            continue

        assessments.append(
            LegalFactAssessment(
                name=missing.name,
                status=LegalFactStatus.MISSING,
                materiality=LegalFactMateriality.MATERIAL,
                basis=missing.reason,
                requires_clarification=True,
            )
        )

    return assessments
