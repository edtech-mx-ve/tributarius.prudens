from __future__ import annotations

from statistics import fmean

from pydantic import BaseModel, Field


class EvaluationError(ValueError):
    """Error de datos de evaluación RAG."""


class QueryEvaluation(BaseModel):
    query_id: str
    recall_at_k: float = Field(ge=0.0, le=1.0)
    precision_at_k: float = Field(ge=0.0, le=1.0)
    reciprocal_rank: float = Field(ge=0.0, le=1.0)
    hit_rate: float = Field(ge=0.0, le=1.0)


class EvaluationSummary(BaseModel):
    k: int = Field(ge=1)
    query_count: int = Field(ge=1)
    recall_at_k: float
    precision_at_k: float
    mrr: float
    hit_rate: float
    queries: list[QueryEvaluation]


def evaluate_retrieval(
    expected: dict[str, set[str]],
    retrieved: dict[str, list[str]],
    *,
    k: int,
) -> EvaluationSummary:
    if k < 1:
        raise EvaluationError("k debe ser mayor o igual a 1.")
    if not expected:
        raise EvaluationError("Se requiere al menos una consulta evaluable.")

    details: list[QueryEvaluation] = []
    for query_id, relevant in expected.items():
        if not relevant:
            raise EvaluationError(
                f"La consulta '{query_id}' no contiene chunks relevantes."
            )
        ranked = retrieved.get(query_id, [])[:k]
        relevant_hits = [chunk_id for chunk_id in ranked if chunk_id in relevant]
        unique_hits = set(relevant_hits)

        recall = len(unique_hits) / len(relevant)
        precision = len(relevant_hits) / k
        first_rank = next(
            (rank for rank, chunk_id in enumerate(ranked, start=1)
             if chunk_id in relevant),
            None,
        )
        reciprocal_rank = 0.0 if first_rank is None else 1.0 / first_rank
        hit_rate = 1.0 if relevant_hits else 0.0
        details.append(
            QueryEvaluation(
                query_id=query_id,
                recall_at_k=recall,
                precision_at_k=precision,
                reciprocal_rank=reciprocal_rank,
                hit_rate=hit_rate,
            )
        )

    return EvaluationSummary(
        k=k,
        query_count=len(details),
        recall_at_k=fmean(item.recall_at_k for item in details),
        precision_at_k=fmean(item.precision_at_k for item in details),
        mrr=fmean(item.reciprocal_rank for item in details),
        hit_rate=fmean(item.hit_rate for item in details),
        queries=details,
    )
