from __future__ import annotations

import collections.abc
import copy
import typing

_POLICY = "evidence_bound_fail_closed"


def _count_items(value: typing.Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _has_text(value: typing.Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def explanation_integrity_status(
    result: collections.abc.Mapping[str, typing.Any],
) -> str:
    """Classify the public explanation without inferring legal validity.

    The classifier is deliberately conservative. It never promotes a norm,
    changes retrieval, changes human-review decisions, or rewrites the
    explanation. It only exposes the integrity state that a future LLM layer
    must respect.
    """
    explanation = result.get("explanation")
    if not _has_text(explanation):
        return "not_generated"

    review_required = result.get("requires_human_review") is True
    applicable_count = _count_items(result.get("applicable_normative_refs"))
    evidence_count = _count_items(result.get("evidence"))

    if applicable_count > 0 and not review_required:
        return "grounded_applicable_norm"

    if review_required and applicable_count == 0:
        if evidence_count > 0:
            return "evidence_only_review_required"
        return "review_required_without_evidence"

    if evidence_count > 0:
        return "evidence_present_no_applicability_claim"

    return "ungrounded"


def build_explanation_integrity(
    result: collections.abc.Mapping[str, typing.Any],
) -> dict[str, typing.Any]:
    """Build auditable explanation-integrity metadata."""
    return {
        "policy": _POLICY,
        "status": explanation_integrity_status(result),
        "evidence_count": _count_items(result.get("evidence")),
        "applicable_normative_ref_count": _count_items(
            result.get("applicable_normative_refs")
        ),
        "requires_human_review": result.get("requires_human_review") is True,
        "llm_authority": "none",
    }


def reconcile_public_explanation_payload(payload: typing.Any) -> typing.Any:
    """Attach explanation-integrity metadata to JSON-like public responses.

    Input is not mutated. Existing explanation text is preserved byte-for-byte
    at this stage; Unicode normalization remains the responsibility of the
    public response middleware.
    """
    if not isinstance(payload, collections.abc.Mapping):
        return payload

    copied = copy.deepcopy(dict(payload))
    result = copied.get("result")
    if not isinstance(result, collections.abc.Mapping):
        return copied

    result_copy = dict(result)
    result_copy["explanation_integrity"] = build_explanation_integrity(
        result_copy
    )
    copied["result"] = result_copy
    return copied
