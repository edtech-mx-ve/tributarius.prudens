import numpy as np
import pytest

from rag.embeddings.provider import (
    EmbeddingError,
    SentenceTransformerEmbedder,
    normalize_rows,
    validate_model_id,
)


def test_normalize_rows_returns_unit_vectors() -> None:
    vectors = np.asarray([[3.0, 4.0], [1.0, 0.0]], dtype=np.float32)

    normalized = normalize_rows(vectors)

    assert normalized.dtype == np.float32
    assert np.allclose(np.linalg.norm(normalized, axis=1), [1.0, 1.0])


def test_normalize_rows_rejects_zero_vector() -> None:
    with pytest.raises(EmbeddingError, match="norma cero"):
        normalize_rows(np.asarray([[0.0, 0.0]], dtype=np.float32))


def test_validate_model_id_rejects_path_traversal() -> None:
    with pytest.raises(EmbeddingError):
        validate_model_id("../modelo")


def test_embedder_rejects_non_cpu_device() -> None:
    with pytest.raises(EmbeddingError, match="cpu"):
        SentenceTransformerEmbedder(device="cuda")
