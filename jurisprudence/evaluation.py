from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.jurisprudence import JurisprudenceRetrievalResult


class JurisprudenceEvaluationResult(BaseModel):
    activation_accuracy: float = Field(ge=0.0, le=1.0)
    relevance_precision: float = Field(ge=0.0, le=1.0)
    norm_relation_recall: float = Field(ge=0.0, le=1.0)
    spurious_retrieval_rate: float = Field(ge=0.0, le=1.0)
    passed: bool


def evaluate_jurisprudence_retrieval(
    result: JurisprudenceRetrievalResult,
    *,
    expected_activated: bool,
    expected_document_ids: set[str],
    expected_norm_related_document_ids: set[str],
) -> JurisprudenceEvaluationResult:
    activation_accuracy = 1.0 if result.activated == expected_activated else 0.0
    actual_ids = {hit.metadata.document_id for hit in result.hits}

    if actual_ids:
        relevance_precision = len(actual_ids & expected_document_ids) / len(actual_ids)
    else:
        relevance_precision = 1.0 if not expected_document_ids else 0.0

    related_actual = {
        hit.metadata.document_id
        for hit in result.hits
        if hit.assessment.relevant_to_norm
    }
    if expected_norm_related_document_ids:
        norm_relation_recall = (
            len(related_actual & expected_norm_related_document_ids)
            / len(expected_norm_related_document_ids)
        )
    else:
        norm_relation_recall = 1.0 if not related_actual else 0.0

    if result.hits:
        spurious = len(actual_ids - expected_document_ids)
        spurious_retrieval_rate = spurious / len(result.hits)
    else:
        spurious_retrieval_rate = 0.0

    passed = (
        activation_accuracy == 1.0
        and relevance_precision >= 0.95
        and norm_relation_recall >= 0.80
        and spurious_retrieval_rate <= 0.05
    )
    return JurisprudenceEvaluationResult(
        activation_accuracy=activation_accuracy,
        relevance_precision=relevance_precision,
        norm_relation_recall=norm_relation_recall,
        spurious_retrieval_rate=spurious_retrieval_rate,
        passed=passed,
    )
