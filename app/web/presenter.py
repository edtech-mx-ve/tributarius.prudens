from __future__ import annotations

from app.domain.traceability import CanonicalExecutionResult
from app.web.schemas import WebConsultationRequest


def _safe_explanation(result: CanonicalExecutionResult) -> str | None:
    explanation = result.explanation
    if not isinstance(explanation, dict):
        return None
    answer = explanation.get("answer")
    if not isinstance(answer, dict):
        return None
    value = answer.get("answer")
    return value if isinstance(value, str) else None


def present_canonical_result(
    result: CanonicalExecutionResult,
    request: WebConsultationRequest,
) -> dict[str, object]:
    """Proyección web: reduce el canónico sin recalcular ni reinterpretar."""
    evidence = [
        {
            "ref_id": item.ref_id,
            "kind": item.kind.value,
            "source_type": item.source_type,
            "source_reference": item.source_reference,
            "version": item.version,
            "fiscal_year": item.fiscal_year,
            "score": item.score,
        }
        for item in result.traceability.evidence
    ]
    uncertainties = [
        item.model_dump(mode="json")
        for item in result.traceability.uncertainties
    ]
    return {
        "folio": result.folio,
        "mode": request.mode,
        "requires_human_review": result.traceability.requires_human_review,
        "explanation": _safe_explanation(result),
        "applicable_normative_refs": result.normative.get(
            "applicable_refs",
            [],
        ),
        "calculations": result.calculations,
        "cbr": result.cbr,
        "evidence": evidence,
        "uncertainties": uncertainties,
    }
