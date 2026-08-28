from __future__ import annotations

from collections.abc import Iterable


def exact_match(expected: object, actual: object) -> float:
    return 1.0 if expected == actual else 0.0


def set_precision(expected: Iterable[str], actual: Iterable[str]) -> float:
    expected_set = set(expected)
    actual_set = set(actual)
    if not actual_set:
        return 1.0 if not expected_set else 0.0
    return len(expected_set & actual_set) / len(actual_set)


def set_recall(expected: Iterable[str], actual: Iterable[str]) -> float:
    expected_set = set(expected)
    actual_set = set(actual)
    if not expected_set:
        return 1.0 if not actual_set else 0.0
    return len(expected_set & actual_set) / len(expected_set)


def recall_at_k(
    expected: Iterable[str],
    ranked_actual: Iterable[str],
    *,
    k: int,
) -> float:
    if k < 1:
        raise ValueError("k debe ser >= 1.")
    expected_set = set(expected)
    if not expected_set:
        return 1.0
    actual = list(ranked_actual)[:k]
    return len(expected_set & set(actual)) / len(expected_set)


def mean(values: Iterable[float]) -> float:
    materialized = list(values)
    if not materialized:
        raise ValueError("Se requiere al menos un valor.")
    return sum(materialized) / len(materialized)
