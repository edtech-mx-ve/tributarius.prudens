from __future__ import annotations

from collections.abc import Iterable

from app.domain.normative import (
    NormativeApplicabilityRequest,
    NormativeApplicabilityResult,
    NormativeDecision,
    NormativeSelectionRequest,
    NormativeValidityBasis,
    NormativeValidityScope,
    NormativeValidityStatus,
    NormativeVersionView,
)


def _result(
    request: NormativeApplicabilityRequest,
    *,
    decision: NormativeDecision,
    applicable: bool,
    reason: str,
    requires_human_review: bool = False,
) -> NormativeApplicabilityResult:
    return NormativeApplicabilityResult(
        legal_unit_id=request.legal_unit_id,
        version_label=request.version_label,
        decision=decision,
        applicable=applicable,
        query_date=request.query_date,
        query_fiscal_year=request.query_fiscal_year,
        effective_from=request.effective_from,
        effective_to=request.effective_to,
        fiscal_year=request.fiscal_year,
        validity_status=request.validity_status,
        validity_scope=request.validity_scope,
        validity_basis=request.validity_basis,
        validity_verified_at=request.validity_verified_at,
        official_source=request.official_source,
        reason=reason,
        requires_human_review=requires_human_review,
    )


def _verified_snapshot_applies(request: NormativeApplicabilityRequest) -> bool:
    return (
        request.validity_status is NormativeValidityStatus.VERIFIED_IN_FORCE
        and request.validity_scope
        in {NormativeValidityScope.DOCUMENT, NormativeValidityScope.LEGAL_UNIT}
        and request.validity_basis
        in {
            NormativeValidityBasis.OFFICIAL_CONSOLIDATED_VERSION,
            NormativeValidityBasis.VERIFIED_REFORM_CHAIN,
        }
        and request.validity_verified_at is not None
        and request.query_date == request.validity_verified_at
        and bool(request.official_source)
    )


def evaluate_normative_applicability(
    request: NormativeApplicabilityRequest,
) -> NormativeApplicabilityResult:
    if request.validity_status is NormativeValidityStatus.CONFLICTING:
        return _result(
            request,
            decision=NormativeDecision.INVALID_DATA,
            applicable=False,
            reason="La evidencia temporal contiene señales contradictorias.",
            requires_human_review=True,
        )

    if request.effective_from is None and request.effective_to is None:
        if _verified_snapshot_applies(request):
            return _result(
                request,
                decision=NormativeDecision.APPLICABLE,
                applicable=True,
                reason=(
                    "La vigencia fue verificada para la fecha consultada mediante "
                    "una fuente oficial y un fundamento de vigencia explícito, sin "
                    "inferir fechas de publicación o reforma."
                ),
            )
        return _result(
            request,
            decision=NormativeDecision.UNKNOWN_VALIDITY,
            applicable=False,
            reason=(
                "La versión no contiene límites de vigencia suficientes ni una "
                "verificación de vigencia válida para la fecha consultada."
            ),
            requires_human_review=True,
        )

    if (
        request.effective_from is not None
        and request.query_date < request.effective_from
    ):
        return _result(
            request,
            decision=NormativeDecision.NOT_YET_EFFECTIVE,
            applicable=False,
            reason="La fecha consultada es anterior al inicio de vigencia.",
        )

    if request.effective_to is not None and request.query_date > request.effective_to:
        return _result(
            request,
            decision=NormativeDecision.EXPIRED,
            applicable=False,
            reason="La fecha consultada es posterior al fin de vigencia.",
        )

    if (
        request.fiscal_year is not None
        and request.query_fiscal_year is not None
        and request.fiscal_year != request.query_fiscal_year
    ):
        return _result(
            request,
            decision=NormativeDecision.FISCAL_YEAR_MISMATCH,
            applicable=False,
            reason="El ejercicio fiscal de la versión no coincide con el consultado.",
        )

    return _result(
        request,
        decision=NormativeDecision.APPLICABLE,
        applicable=True,
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
                validity_status=version.validity_status,
                validity_scope=version.validity_scope,
                validity_basis=version.validity_basis,
                validity_verified_at=version.validity_verified_at,
                official_source=version.official_source,
                query_date=request.query_date,
                query_fiscal_year=request.query_fiscal_year,
            )
        )
        for version in versions
    ]
    return [result for result in results if result.applicable]
