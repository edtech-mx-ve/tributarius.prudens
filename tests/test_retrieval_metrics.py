import pytest

from rag.evaluation.metrics import EvaluationError, evaluate_retrieval


def test_evaluate_retrieval_metrics() -> None:
    expected = {
        "q1": {"a", "b"},
        "q2": {"d"},
    }
    retrieved = {
        "q1": ["x", "a", "b"],
        "q2": ["d", "z"],
    }

    result = evaluate_retrieval(expected, retrieved, k=3)

    assert result.recall_at_k == pytest.approx(1.0)
    assert result.precision_at_k == pytest.approx(0.5)
    assert result.mrr == pytest.approx(0.75)
    assert result.hit_rate == pytest.approx(1.0)


def test_evaluate_retrieval_miss() -> None:
    result = evaluate_retrieval({"q": {"a"}}, {"q": ["x", "y"]}, k=2)

    assert result.recall_at_k == 0.0
    assert result.precision_at_k == 0.0
    assert result.mrr == 0.0
    assert result.hit_rate == 0.0


def test_evaluate_retrieval_rejects_empty_relevance() -> None:
    with pytest.raises(EvaluationError):
        evaluate_retrieval({"q": set()}, {"q": []}, k=5)
