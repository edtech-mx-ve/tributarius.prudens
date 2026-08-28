from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

import numpy as np
from numpy.typing import ArrayLike, NDArray

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
_MODEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{2,199}$")


class EmbeddingError(RuntimeError):
    """Error controlado del subsistema de embeddings."""


@runtime_checkable
class EmbeddingProvider(Protocol):
    @property
    def model_name(self) -> str:
        ...

    def encode(self, texts: Sequence[str]) -> NDArray[np.float32]:
        ...


def validate_model_id(model_name: str) -> str:
    value = model_name.strip()
    if not _MODEL_ID_RE.fullmatch(value):
        raise EmbeddingError(
            "Identificador de modelo inválido. Use un identificador Hugging Face simple."
        )
    if ".." in value or value.startswith(("/", "\\")):
        raise EmbeddingError("El identificador del modelo contiene una ruta no permitida.")
    return value


def normalize_rows(vectors: ArrayLike) -> NDArray[np.float32]:
    array = np.asarray(vectors, dtype=np.float32)
    if array.ndim != 2 or array.shape[0] == 0 or array.shape[1] == 0:
        raise EmbeddingError("La matriz de embeddings debe ser bidimensional y no vacía.")
    if not np.isfinite(array).all():
        raise EmbeddingError("Los embeddings contienen NaN o infinitos.")

    norms = np.linalg.norm(array, axis=1, keepdims=True)
    if np.any(norms <= 0):
        raise EmbeddingError("No se permiten embeddings con norma cero.")

    return np.ascontiguousarray(array / norms, dtype=np.float32)


class SentenceTransformerEmbedder:
    def __init__(
        self,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        *,
        batch_size: int = 32,
        device: str = "cpu",
        local_files_only: bool = False,
    ) -> None:
        if batch_size < 1 or batch_size > 1024:
            raise EmbeddingError("batch_size debe estar entre 1 y 1024.")
        if device != "cpu":
            raise EmbeddingError("Sprint 4 admite únicamente device='cpu'.")

        self._model_name = validate_model_id(model_name)
        self._batch_size = batch_size
        self._device = device
        self._local_files_only = local_files_only
        self._model: object | None = None

    @property
    def model_name(self) -> str:
        return self._model_name

    def _load_model(self) -> object:
        if self._model is not None:
            return self._model

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise EmbeddingError(
                "sentence-transformers no está instalado. Ejecute pip install -e '.[dev]'."
            ) from exc

        try:
            self._model = SentenceTransformer(
                self._model_name,
                device=self._device,
                trust_remote_code=False,
                local_files_only=self._local_files_only,
            )
        except Exception as exc:
            raise EmbeddingError(
                f"No fue posible cargar el modelo de embeddings '{self._model_name}'."
            ) from exc

        return self._model

    def encode(self, texts: Sequence[str]) -> NDArray[np.float32]:
        clean_texts = [text.strip() for text in texts]
        if not clean_texts or any(not text for text in clean_texts):
            raise EmbeddingError("Los textos para embeddings no pueden estar vacíos.")

        model = self._load_model()

        try:
            raw = model.encode(  # type: ignore[attr-defined]
                clean_texts,
                batch_size=self._batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        except Exception as exc:
            raise EmbeddingError("Falló la generación de embeddings.") from exc

        return normalize_rows(np.asarray(raw, dtype=np.float32))
