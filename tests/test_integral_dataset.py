import json
from pathlib import Path

import pytest

from evaluation.dataset import EvaluationDatasetError, load_evaluation_dataset


def test_load_integral_smoke_dataset() -> None:
    cases, digest = load_evaluation_dataset(
        Path("evaluation/datasets/integral_smoke.json")
    )
    assert cases[0].case_id == "EVAL-ISR-001"
    assert len(digest) == 64


def test_dataset_rejects_duplicate_ids(tmp_path: Path) -> None:
    case = {
        "case_id": "DUP-001",
        "kind": "normal",
    }
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps([case, case]), encoding="utf-8")
    with pytest.raises(EvaluationDatasetError):
        load_evaluation_dataset(path)


def test_dataset_rejects_unknown_fields(tmp_path: Path) -> None:
    path = tmp_path / "dataset.json"
    path.write_text(
        json.dumps([{"case_id": "BAD-001", "unknown": True}]),
        encoding="utf-8",
    )
    with pytest.raises(EvaluationDatasetError):
        load_evaluation_dataset(path)
