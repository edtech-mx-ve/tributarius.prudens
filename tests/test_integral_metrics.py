import pytest

from evaluation.metrics import exact_match, mean, recall_at_k, set_precision, set_recall


def test_set_metrics() -> None:
    assert set_precision(["a", "b"], ["a", "x"]) == 0.5
    assert set_recall(["a", "b"], ["a", "x"]) == 0.5
    assert recall_at_k(["a", "b"], ["x", "a", "b"], k=2) == 0.5


def test_empty_set_semantics() -> None:
    assert set_precision([], []) == 1.0
    assert set_recall([], []) == 1.0
    assert recall_at_k([], ["x"], k=1) == 1.0


def test_metric_validation() -> None:
    with pytest.raises(ValueError):
        recall_at_k(["a"], ["a"], k=0)
    with pytest.raises(ValueError):
        mean([])


def test_exact_match() -> None:
    assert exact_match({"a"}, {"a"}) == 1.0
    assert exact_match("a", "b") == 0.0
