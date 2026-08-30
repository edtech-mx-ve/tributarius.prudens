from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.services.public_response_quality_19s_r16 import dedupe_evidence

_VISIBLE_FIELDS = (
    "ref_id",
    "document_id",
    "title",
    "unit",
    "snippet",
)


def _has_visible_content(item: Mapping[str, Any]) -> bool:
    """Return True only when an evidence card has user-visible identity/content."""
    for field in _VISIBLE_FIELDS:
        value = item.get(field)
        if isinstance(value, str) and value.strip():
            return True
        if value is not None and not isinstance(value, str):
            return True
    return False


def clean_public_evidence(
    evidence: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Remove exact ref duplicates and structurally empty public evidence cards.

    The first occurrence of a ref_id is preserved. Items without ref_id remain
    eligible when they expose other visible fields. No score, legal status,
    normative applicability, retrieval order, or source text is rewritten.
    """
    deduped = dedupe_evidence(evidence)
    return [item for item in deduped if _has_visible_content(item)]


def reconcile_public_evidence_payload(payload: Any) -> Any:
    """Clean ``result.evidence`` in a JSON-like payload without mutating input."""
    if not isinstance(payload, Mapping):
        return payload

    copied: dict[str, Any] = dict(payload)
    result = copied.get("result")
    if not isinstance(result, Mapping):
        return copied

    result_copy: dict[str, Any] = dict(result)
    evidence = result_copy.get("evidence")
    if not isinstance(evidence, list):
        copied["result"] = result_copy
        return copied

    mappings = [item for item in evidence if isinstance(item, Mapping)]
    non_mappings = [item for item in evidence if not isinstance(item, Mapping)]
    cleaned = clean_public_evidence(mappings)
    result_copy["evidence"] = [*cleaned, *non_mappings]
    copied["result"] = result_copy
    return copied
