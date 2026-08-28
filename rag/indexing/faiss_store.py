from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from rag.embeddings.provider import normalize_rows


class FaissStoreError(RuntimeError):
    """Error controlado del índice FAISS."""


def _import_faiss() -> Any:
    try:
        import faiss
    except ImportError as exc:
        raise FaissStoreError(
            "faiss-cpu no está instalado. Ejecute pip install -e '.[dev]'."
        ) from exc
    return faiss


class FaissVectorStore:
    @staticmethod
    def write(vectors: ArrayLike, path: Path) -> Path:
        normalized = normalize_rows(vectors)
        resolved = path.expanduser().resolve()
        resolved.parent.mkdir(parents=True, exist_ok=True)

        faiss = _import_faiss()
        index = faiss.IndexFlatIP(int(normalized.shape[1]))
        index.add(normalized)
        faiss.write_index(index, str(resolved))
        return resolved

    @staticmethod
    def read(path: Path) -> Any:
        resolved = path.expanduser().resolve()
        if not resolved.exists() or not resolved.is_file():
            raise FaissStoreError(f"No existe el índice FAISS: {resolved}")

        faiss = _import_faiss()
        try:
            return faiss.read_index(str(resolved))
        except Exception as exc:
            raise FaissStoreError("No fue posible leer el índice FAISS.") from exc

    @staticmethod
    def search(
        index: Any,
        query_vector: ArrayLike,
        *,
        top_k: int,
    ) -> tuple[NDArray[np.float32], NDArray[np.int64]]:
        if top_k < 1:
            raise FaissStoreError("top_k debe ser mayor o igual a 1.")

        normalized = normalize_rows(query_vector)
        if normalized.shape[0] != 1:
            raise FaissStoreError("La búsqueda requiere exactamente un vector de consulta.")

        distances, positions = index.search(normalized, top_k)
        return (
            np.asarray(distances[0], dtype=np.float32),
            np.asarray(positions[0], dtype=np.int64),
        )
