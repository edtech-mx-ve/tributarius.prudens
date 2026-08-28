from __future__ import annotations

from datetime import date
from typing import Protocol

from app.domain.documents import SourceType
from app.domain.jurisprudence import (
    JurisprudenceActivationDecision,
    JurisprudenceHit,
    JurisprudenceMetadata,
    JurisprudenceRetrievalResult,
)
from jurisprudence.assessment import assess_jurisprudential_candidate
from rag.retrieval.filters import RetrievalFilters
from rag.retrieval.models import RetrievalResult


class RetrieverLike(Protocol):
    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> RetrievalResult:
        ...


class JurisprudenceRetrievalError(RuntimeError):
    pass


class JurisprudenceRetriever:
    """Frontera que impide mezclar jurisprudencia con otras capas documentales."""

    def __init__(
        self,
        retriever: RetrieverLike,
        metadata_by_document_id: dict[str, JurisprudenceMetadata],
    ) -> None:
        if not metadata_by_document_id:
            raise JurisprudenceRetrievalError(
                "Se requiere un registro jurisprudencial no vacío."
            )
        self._retriever = retriever
        self._metadata = dict(metadata_by_document_id)

    def search(
        self,
        query: str,
        *,
        activation: JurisprudenceActivationDecision,
        query_date: date,
        applicable_normative_refs: set[str],
        top_k: int = 5,
        matter: str | None = None,
    ) -> JurisprudenceRetrievalResult:
        if top_k < 1 or top_k > 20:
            raise JurisprudenceRetrievalError("top_k debe estar entre 1 y 20.")
        if not query.strip():
            raise JurisprudenceRetrievalError("La consulta no puede estar vacía.")
        if not activation.activated:
            return JurisprudenceRetrievalResult(
                activated=False,
                activation=activation,
                candidate_count=0,
                returned_count=0,
                hits=[],
                requires_human_review=activation.requires_human_review,
            )

        raw = self._retriever.search(
            query,
            top_k=max(top_k * 3, top_k),
            filters=RetrievalFilters(
                source_types={SourceType.JURISPRUDENCIA},
                document_ids=set(self._metadata),
            ),
        )

        hits: list[JurisprudenceHit] = []
        review = activation.requires_human_review
        for raw_hit in raw.hits:
            if raw_hit.metadata.source_type != SourceType.JURISPRUDENCIA:
                raise JurisprudenceRetrievalError(
                    "El retriever devolvió una fuente ajena a jurisprudencia."
                )
            metadata = self._metadata.get(raw_hit.metadata.document_id)
            if metadata is None:
                raise JurisprudenceRetrievalError(
                    "Falta metadata jurisprudencial para un documento recuperado."
                )

            assessment = assess_jurisprudential_candidate(
                metadata,
                query_date=query_date,
                applicable_normative_refs=applicable_normative_refs,
                matter=matter,
            )
            review = review or assessment.requires_human_review
            if not assessment.eligible:
                continue

            hits.append(
                JurisprudenceHit(
                    rank=len(hits) + 1,
                    score=raw_hit.score,
                    chunk_id=raw_hit.chunk_id,
                    text=raw_hit.text,
                    metadata=metadata,
                    assessment=assessment,
                )
            )
            if len(hits) >= top_k:
                break

        return JurisprudenceRetrievalResult(
            activated=True,
            activation=activation,
            candidate_count=raw.candidate_count,
            returned_count=len(hits),
            hits=hits,
            requires_human_review=review,
        )
