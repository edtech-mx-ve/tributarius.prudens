from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Protocol

from app.domain.documents import SourceType
from app.domain.jurisprudence import (
    JurisprudenceActivationDecision,
    JurisprudenceHit,
    JurisprudenceMetadata,
    JurisprudenceRetrievalResult,
)
from app.domain.jurisprudence_document import JurisprudenceDocumentRepresentation
from app.domain.jurisprudence_session_retrieval import (
    SessionJurisprudenceHit,
    SessionJurisprudenceRetrievalResult,
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


_TOKEN_RE = re.compile(r"[a-z0-9]+", flags=re.IGNORECASE)


def _normalized_tokens(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return set(_TOKEN_RE.findall(ascii_text))


def _lexical_score(query_tokens: set[str], text: str) -> float:
    text_tokens = _normalized_tokens(text)
    if not query_tokens or not text_tokens:
        return 0.0
    overlap = len(query_tokens & text_tokens)
    return overlap / len(query_tokens)


class SessionJurisprudenceRetriever:
    """Recupera páginas de PDFs temporales sin decidir su aplicabilidad jurídica."""

    def __init__(
        self,
        documents: list[JurisprudenceDocumentRepresentation],
    ) -> None:
        if not documents:
            raise JurisprudenceRetrievalError(
                "Se requiere al menos un documento jurisprudencial de sesión."
            )
        document_ids = [document.document_id for document in documents]
        if len(document_ids) != len(set(document_ids)):
            raise JurisprudenceRetrievalError(
                "Los documentos jurisprudenciales de sesión no pueden repetirse."
            )
        self._documents = list(documents)

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        minimum_score: float = 0.0,
    ) -> SessionJurisprudenceRetrievalResult:
        clean_query = query.strip()
        if not clean_query:
            raise JurisprudenceRetrievalError("La consulta no puede estar vacía.")
        if top_k < 1 or top_k > 20:
            raise JurisprudenceRetrievalError("top_k debe estar entre 1 y 20.")
        if minimum_score < 0.0 or minimum_score > 1.0:
            raise JurisprudenceRetrievalError(
                "minimum_score debe estar entre 0 y 1."
            )

        query_tokens = _normalized_tokens(clean_query)
        candidates: list[tuple[float, str, int, JurisprudenceDocumentRepresentation, str]] = []

        for document in self._documents:
            for page in document.pages:
                if not page.has_extractable_text or not page.text.strip():
                    continue
                score = _lexical_score(query_tokens, page.text)
                if score <= 0.0 or score < minimum_score:
                    continue
                candidates.append(
                    (
                        score,
                        document.document_id,
                        page.number,
                        document,
                        page.text,
                    )
                )

        candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
        selected = candidates[:top_k]

        hits = [
            SessionJurisprudenceHit(
                rank=index,
                score=score,
                document_id=document.document_id,
                original_filename=document.original_filename,
                source_sha256=document.source_sha256,
                page_number=page_number,
                text=text,
            )
            for index, (score, _, page_number, document, text) in enumerate(
                selected,
                start=1,
            )
        ]

        return SessionJurisprudenceRetrievalResult(
            query=clean_query,
            candidate_count=len(candidates),
            returned_count=len(hits),
            hits=hits,
        )
