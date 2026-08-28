from pathlib import Path

import pytest

from rag.evaluation.dataset import load_evaluation_dataset
from rag.evaluation.metrics import EvaluationError


def test_load_evaluation_dataset(tmp_path: Path) -> None:
    path = tmp_path / "eval.jsonl"
    path.write_text(
        '{"query_id":"q1","query":"ISR","relevant_chunk_ids":["a"]}\n',
        encoding="utf-8",
    )

    cases = load_evaluation_dataset(path)

    assert len(cases) == 1
    assert cases[0].query_id == "q1"


def test_dataset_rejects_duplicate_query_id(tmp_path: Path) -> None:
    path = tmp_path / "eval.jsonl"
    path.write_text(
        '{"query_id":"q1","query":"ISR","relevant_chunk_ids":["a"]}\n'
        '{"query_id":"q1","query":"IVA","relevant_chunk_ids":["b"]}\n',
        encoding="utf-8",
    )

    with pytest.raises(EvaluationError, match="duplicado"):
        load_evaluation_dataset(path)
