from __future__ import annotations

from typing import Any

from app.domain.legal_decision import LegalDecision
from app.services.traceability import canonical_sha256


def legal_decision_sha256(decision: LegalDecision) -> str:
    """Huella determinista de Legal Decision 1.0, separada del canónico histórico."""
    payload: dict[str, Any] = decision.model_dump(mode="json")
    return canonical_sha256(payload)


def verify_legal_decision_integrity(
    decision: LegalDecision,
    expected_sha256: str,
) -> bool:
    """Verifica que Legal Decision 1.0 no haya sido alterada."""
    return legal_decision_sha256(decision) == expected_sha256
