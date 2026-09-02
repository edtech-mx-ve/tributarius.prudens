from __future__ import annotations

from typing import Any

from app.domain.integral_legal_analysis import IntegralLegalAnalysis
from app.services.traceability import canonical_sha256


def integral_legal_analysis_sha256(
    analysis: IntegralLegalAnalysis,
) -> str:
    """Huella determinista del Analyzer 1.0, separada del canónico histórico."""

    payload: dict[str, Any] = analysis.model_dump(mode="json")
    return canonical_sha256(payload)


def verify_integral_legal_analysis_integrity(
    analysis: IntegralLegalAnalysis,
    expected_sha256: str,
) -> bool:
    """Verifica que la proyección jurídica integral no haya sido alterada."""

    return integral_legal_analysis_sha256(analysis) == expected_sha256
