"""Sprint 19I.18S-r15.1 compatibility helpers.

Pure functions used to read QueryAnalysis facts defensively.  Pydantic's
``model_copy(update=...)`` does not validate nested update values, so tests and
internal callers can legitimately expose mapping-shaped facts.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def fact_value(fact: object, field: str) -> Any | None:
    """Return a field from either a model-like fact or a mapping."""
    if isinstance(fact, Mapping):
        return fact.get(field)
    return getattr(fact, field, None)


def query_fact_value(facts: Sequence[object], name: str) -> str | None:
    """Return the first non-empty fact value matching ``name``."""
    expected = name.strip().casefold()
    for fact in facts:
        raw_name = fact_value(fact, "name")
        if not isinstance(raw_name, str) or raw_name.strip().casefold() != expected:
            continue
        raw_value = fact_value(fact, "value")
        if raw_value is None:
            return None
        value = str(raw_value).strip()
        return value or None
    return None
