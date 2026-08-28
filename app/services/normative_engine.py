from __future__ import annotations

from collections.abc import Iterable

from app.domain.normative import (
    NormativeApplicabilityRequest,
    NormativeApplicabilityResult,
    NormativeDecision,
    NormativeSelectionRequest,
    NormativeVersionView,
)


def evaluate_normative_applicability(
    request: NormativeApplicabilityRequest,
) -> NormativeApplicabilityResult:
    if request.effective_from is None and request.effective_to is None:
        return NormativeApplicabilityResult(
            legal_unit_id=request.legal_unit_id,
            version_label=request.version_label,
            decision=NormativeDecision.UNKNOWN_VALIDITY,
            applicable=False,
            query_date=request.query_date,
            query_fiscal_year=request.query_fiscal_year,
            effective_from=request.effective_from,
            effective_to=request.effective_to,
            fiscal_year=request.fiscal_year,
            reason=(
                "La versión no contiene límites de vigencia suficientes para "
                "demostrar aplicabilidad temporal."
            ),
            requires_human_review=True,
        )

    if (
        request.effective_from is not None
        and request.query_date < request.effective_from
    ):
        return NormativeApplicabilityResult(
            legal_unit_id=request.legal_unit_id,
            version_label=request.version_label,
            decision=NormativeDecision.NOT_YET_EFFECTIVE,
            applicable=False,
            query_date=request.query_date,
            query_fiscal_year=request.query_fiscal_year,
            effective_from=request.effective_from,
            effective_to=request.effective_to,
            fiscal_year=request.fiscal_year,
            reason="La fecha consultada es anterior al inicio de vigencia.",
        )

    if request.effective_to is not None and request.query_date > request.effective_to:
        return NormativeApplicabilityResult(
            legal_unit_id=request.legal_unit_id,
            version_label=request.version_label,
            decision=NormativeDecision.EXPIRED,
            applicable=False,
            query_date=request.query_date,
            query_fiscal_year=request.query_fiscal_year,
            effective_from=request.effective_from,
            effective_to=request.effective_to,
            fiscal_year=request.fiscal_year,
            reason="La fecha consultada es posterior al fin de vigencia.",
        )

    if (
        request.fiscal_year is not None
        and request.query_fiscal_year is not None
        and request.fiscal_year != request.query_fiscal_year
    ):
        return NormativeApplicabilityResult(
            legal_unit_id=request.legal_unit_id,
            version_label=request.version_label,
            decision=NormativeDecision.FISCAL_YEAR_MISMATCH,
            applicable=False,
            query_date=request.query_date,
            query_fiscal_year=request.query_fiscal_year,
            effective_from=request.effective_from,
            effective_to=request.effective_to,
            fiscal_year=request.fiscal_year,
            reason="El ejercicio fiscal de la versión no coincide con el consultado.",
        )

    return NormativeApplicabilityResult(
        legal_unit_id=request.legal_unit_id,
        version_label=request.version_label,
        decision=NormativeDecision.APPLICABLE,
        applicable=True,
        query_date=request.query_date,
        query_fiscal_year=request.query_fiscal_year,
        effective_from=request.effective_from,
        effective_to=request.effective_to,
        fiscal_year=request.fiscal_year,
        reason="La versión satisface los criterios temporales disponibles.",
    )


def select_applicable_versions(
    request: NormativeSelectionRequest,
    versions: Iterable[NormativeVersionView],
) -> list[NormativeApplicabilityResult]:
    results = [
        evaluate_normative_applicability(
            NormativeApplicabilityRequest(
                legal_unit_id=request.legal_unit_id,
                version_label=version.version_label,
                effective_from=version.effective_from,
                effective_to=version.effective_to,
                fiscal_year=version.fiscal_year,
                query_date=request.query_date,
                query_fiscal_year=request.query_fiscal_year,
            )
        )
        for version in versions
    ]
    return [result for result in results if result.applicable]
