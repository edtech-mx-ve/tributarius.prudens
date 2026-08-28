from pathlib import Path

import numpy as np
import pytest

from rag.indexing.faiss_store import FaissStoreError, FaissVectorStore


class FakeIndex:
    def search(
        self, query: np.ndarray, top_k: int
    ) -> tuple[np.ndarray, np.ndarray]:
        assert query.shape == (1, 2)
        return (
            np.asarray([[0.9, 0.4]], dtype=np.float32),
            np.asarray([[2, 0]], dtype=np.int64),
        )


def test_vector_store_search_returns_flat_arrays() -> None:
    scores, positions = FaissVectorStore.search(
        FakeIndex(),
        np.asarray([[3.0, 4.0]], dtype=np.float32),
        top_k=2,
    )

    assert scores.tolist() == pytest.approx([0.9, 0.4])
    assert positions.tolist() == [2, 0]


def test_vector_store_search_rejects_invalid_top_k() -> None:
    with pytest.raises(FaissStoreError, match="top_k"):
        FaissVectorStore.search(
            FakeIndex(),
            np.asarray([[1.0, 0.0]], dtype=np.float32),
            top_k=0,
        )


def test_vector_store_read_rejects_missing_index(tmp_path: Path) -> None:
    with pytest.raises(FaissStoreError, match="No existe"):
        FaissVectorStore.read(tmp_path / "missing.faiss")
