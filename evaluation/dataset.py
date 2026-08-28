from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from evaluation.models import EvaluationCase

_MAX_DATASET_BYTES = 5 * 1024 * 1024
_CASE_LIST = TypeAdapter(list[EvaluationCase])


class EvaluationDatasetError(ValueError):
    pass


def load_evaluation_dataset(path: Path) -> tuple[list[EvaluationCase], str]:
    if path.suffix.lower() != ".json":
        raise EvaluationDatasetError("El dataset debe usar formato JSON.")
    if not path.is_file():
        raise EvaluationDatasetError("No se encontró el dataset de evaluación.")
    raw = path.read_bytes()
    if len(raw) > _MAX_DATASET_BYTES:
        raise EvaluationDatasetError("El dataset excede 5 MiB.")
    digest = hashlib.sha256(raw).hexdigest()
    try:
        payload = json.loads(raw.decode("utf-8"))
        cases = _CASE_LIST.validate_python(payload)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
        raise EvaluationDatasetError("Dataset de evaluación inválido.") from exc
    if not cases:
        raise EvaluationDatasetError("El dataset debe contener al menos un caso.")
    ids = [case.case_id for case in cases]
    if len(ids) != len(set(ids)):
        raise EvaluationDatasetError("Los case_id no pueden repetirse.")
    return cases, digest
