from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from rag.evaluation.metrics import EvaluationError


class EvaluationCase(BaseModel):
    query_id: str = Field(min_length=1, max_length=100)
    query: str = Field(min_length=1)
    relevant_chunk_ids: set[str] = Field(min_length=1)


def load_evaluation_dataset(path: Path) -> list[EvaluationCase]:
    resolved = path.expanduser().resolve()
    if not resolved.exists() or not resolved.is_file():
        raise EvaluationError(f"No existe el dataset: {resolved}")

    cases: list[EvaluationCase] = []
    seen: set[str] = set()
    try:
        with resolved.open("r", encoding="utf-8") as handle:
            for line_number, raw in enumerate(handle, start=1):
                if not raw.strip():
                    continue
                try:
                    case = EvaluationCase.model_validate(json.loads(raw))
                except (json.JSONDecodeError, ValidationError) as exc:
                    raise EvaluationError(
                        f"Caso inválido en línea {line_number}."
                    ) from exc
                if case.query_id in seen:
                    raise EvaluationError(
                        f"query_id duplicado: {case.query_id}"
                    )
                seen.add(case.query_id)
                cases.append(case)
    except OSError as exc:
        raise EvaluationError("No fue posible leer el dataset.") from exc

    if not cases:
        raise EvaluationError("El dataset de evaluación está vacío.")
    return cases
