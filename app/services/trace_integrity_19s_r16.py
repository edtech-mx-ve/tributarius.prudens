from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def normative_trace_review_required(
    *,
    global_review_required: bool,
    applicable_refs: Sequence[object],
    has_normative_evidence: bool,
) -> bool:
    """Propaga revisión al stage normativo sólo cuando la abstención la justifica."""
    return bool(
        global_review_required
        and has_normative_evidence
        and not applicable_refs
    )


def normative_trace_summary(
    *,
    applicable_count: int,
    review_required: bool,
) -> str:
    """Construye un resumen auditable del resultado del gate normativo."""
    base = f"Referencias normativas aplicables: {applicable_count}."
    if not review_required:
        return base
    return (
        f"{base} La evidencia recuperada no superó todos los gates de "
        "aplicabilidad; se requiere revisión humana."
    )


def reconcile_traceability_payload(payload: Any) -> Any:
    """Alinea una respuesta serializada sin alterar el resultado jurídico.

    Opera sobre dict/list para poder aplicarse en la frontera de presentación.
    Sólo modifica el evento `normative` cuando el resultado global ya exige
    revisión, hay evidencia normativa recuperada y no existen refs aplicables.
    """
    if not isinstance(payload, Mapping):
        return payload

    result = payload.get("result")
    if not isinstance(result, Mapping):
        return payload

    global_review = bool(result.get("requires_human_review"))
    applicable = result.get("applicable_normative_refs")
    applicable_refs = applicable if isinstance(applicable, list) else []

    evidence = result.get("evidence")
    evidence_items = evidence if isinstance(evidence, list) else []
    has_normative = any(
        isinstance(item, Mapping)
        and (
            item.get("role") == "normative"
            or item.get("source_type") == "normativa"
        )
        for item in evidence_items
    )

    review_required = normative_trace_review_required(
        global_review_required=global_review,
        applicable_refs=applicable_refs,
        has_normative_evidence=has_normative,
    )
    if not review_required:
        return payload

    traceability = result.get("traceability")
    if not isinstance(traceability, Mapping):
        return payload
    events = traceability.get("events")
    if not isinstance(events, list):
        return payload

    copied = _deep_copy_jsonish(payload)
    copied_result = copied["result"]
    copied_events = copied_result["traceability"]["events"]
    for event in copied_events:
        if isinstance(event, dict) and event.get("stage") == "normative":
            event["requires_human_review"] = True
            event["summary"] = normative_trace_summary(
                applicable_count=len(applicable_refs),
                review_required=True,
            )
            break
    return copied


def _deep_copy_jsonish(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _deep_copy_jsonish(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_deep_copy_jsonish(item) for item in value]
    return value
