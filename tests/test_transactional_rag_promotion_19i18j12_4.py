from __future__ import annotations

from pathlib import Path

import pytest

from app.services.transactional_rag_promotion import (
    TransactionalRagPromotionError,
    benchmark_passes,
    parse_retrieval_metrics,
)
from app.services.transactional_rag_promotion import (
    _transactional_promote as transactional_promote,
)

GOOD_OUTPUT = """
Hit@1(any)=1.000
Hit@3(any)=1.000
Hit@K(any)=1.000
MRR(any)=1.000
PrimaryHit@1=0.917
PrimaryHit@3=0.917
PrimaryHit@K=1.000
PrimaryMRR=0.938
MeanUniqueDocs@K=2.333
"""


def test_parse_and_accept_reference_metrics() -> None:
    metrics = parse_retrieval_metrics(GOOD_OUTPUT)
    assert benchmark_passes(metrics)
    assert metrics["PrimaryMRR"] == 0.938


def test_benchmark_rejects_regression() -> None:
    metrics = parse_retrieval_metrics(GOOD_OUTPUT)
    metrics["PrimaryHit@1"] = 0.916
    assert not benchmark_passes(metrics)


def test_missing_metric_fails_closed() -> None:
    with pytest.raises(TransactionalRagPromotionError):
        parse_retrieval_metrics("Hit@1(any)=1.000\n")


def test_transactional_promote_creates_snapshot(tmp_path: Path) -> None:
    source_file = tmp_path / "new.txt"
    source_dir = tmp_path / "newdir"
    target_file = tmp_path / "target.txt"
    target_dir = tmp_path / "targetdir"
    snapshot = tmp_path / "snapshot"

    source_file.write_text("new", encoding="utf-8")
    source_dir.mkdir()
    (source_dir / "x.txt").write_text("new-dir", encoding="utf-8")
    target_file.write_text("old", encoding="utf-8")
    target_dir.mkdir()
    (target_dir / "x.txt").write_text("old-dir", encoding="utf-8")

    transactional_promote(
        [(source_file, target_file), (source_dir, target_dir)],
        snapshot,
    )

    assert target_file.read_text(encoding="utf-8") == "new"
    assert (target_dir / "x.txt").read_text(encoding="utf-8") == "new-dir"
    assert (snapshot / "00_target.txt").read_text(encoding="utf-8") == "old"
    assert (
        snapshot / "01_targetdir" / "x.txt"
    ).read_text(encoding="utf-8") == "old-dir"
