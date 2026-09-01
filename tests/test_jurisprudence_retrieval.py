from datetime import date
from pathlib import Path

import pytest

from app.domain.chunks import ChunkMetadata, LegalChunkType, LegalHierarchy
from app.domain.documents import SourceType
from app.domain.jurisprudence import JurisprudenceActivationDecision
from jurisprudence.loader import load_jurisprudence_metadata
from jurisprudence.retrieval import (
    JurisprudenceRetrievalError,
    JurisprudenceRetriever,
)
from rag.retrieval.filters import RetrievalFilters
from rag.retrieval.models import RetrievalHit, RetrievalResult


class FakeRetriever:
    def __init__(self, result: RetrievalResult) -> None:
        self.result = result
        self.last_filters: RetrievalFilters | None = None

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> RetrievalResult:
        del query, top_k
        self.last_filters = filters
        return self.result


def chunk_metadata(
    document_id: str,
    source_type: SourceType = SourceType.JURISPRUDENCIA,
) -> ChunkMetadata:
    return ChunkMetadata(
        document_id=document_id,
        source_type=source_type,
        source_filename=f"{document_id}.md",
        chunk_index=0,
        chunk_type=LegalChunkType.PARAGRAPH,
        legal_identifier="Criterio sintético",
        page_start=1,
        page_end=1,
        hierarchy=LegalHierarchy(),
        source_sha256="a" * 64,
    )


def raw_result(
    document_ids: list[str],
    *,
    source_type: SourceType = SourceType.JURISPRUDENCIA,
) -> RetrievalResult:
    hits = [
        RetrievalHit(
            rank=index,
            score=0.95 - index / 100,
            chunk_id=f"{document_id}-chunk-0001",
            text="Texto jurisprudencial sintético.",
            metadata=chunk_metadata(document_id, source_type),
        )
        for index, document_id in enumerate(document_ids, start=1)
    ]
    return RetrievalResult(
        query="criterio fiscal",
        requested_top_k=10,
        candidate_count=len(hits),
        returned_count=len(hits),
        hits=hits,
    )


def activated() -> JurisprudenceActivationDecision:
    return JurisprudenceActivationDecision(
        activated=True,
        reason="explicit_request",
        detail="Solicitud explícita.",
    )


def test_retrieval_is_separate_and_excludes_superseded_candidate() -> None:
    registry = load_jurisprudence_metadata(
        Path("jurisprudence/fixtures/metadata_synthetic.jsonl")
    )
    fake = FakeRetriever(
        raw_result(["jur-test-current", "jur-test-superseded"])
    )
    service = JurisprudenceRetriever(fake, registry)

    result = service.search(
        "criterio fiscal",
        activation=activated(),
        query_date=date(2026, 8, 28),
        applicable_normative_refs={"NORM_TEST_ISR_2026"},
        top_k=5,
        matter="fiscal",
    )

    assert fake.last_filters is not None
    assert fake.last_filters.source_types == {SourceType.JURISPRUDENCIA}
    assert result.returned_count == 1
    assert result.hits[0].metadata.document_id == "jur-test-current"


def test_disabled_activation_does_not_call_underlying_retriever() -> None:
    registry = load_jurisprudence_metadata(
        Path("jurisprudence/fixtures/metadata_synthetic.jsonl")
    )

    class ExplodingRetriever:
        def search(
            self,
            query: str,
            *,
            top_k: int = 5,
            filters: RetrievalFilters | None = None,
        ) -> RetrievalResult:
            del query, top_k, filters
            raise AssertionError("No debe ejecutarse recuperación.")

    service = JurisprudenceRetriever(ExplodingRetriever(), registry)
    decision = JurisprudenceActivationDecision(
        activated=False,
        reason="not_needed",
        detail="No requerida.",
    )
    result = service.search(
        "consulta fiscal",
        activation=decision,
        query_date=date(2026, 8, 28),
        applicable_normative_refs=set(),
    )
    assert result.activated is False
    assert result.hits == []


def test_non_jurisprudence_hit_is_rejected() -> None:
    registry = load_jurisprudence_metadata(
        Path("jurisprudence/fixtures/metadata_synthetic.jsonl")
    )
    fake = FakeRetriever(
        raw_result(["jur-test-current"], source_type=SourceType.NORMATIVA)
    )
    service = JurisprudenceRetriever(fake, registry)
    with pytest.raises(JurisprudenceRetrievalError):
        service.search(
            "consulta",
            activation=activated(),
            query_date=date(2026, 8, 28),
            applicable_normative_refs={"NORM_TEST_ISR_2026"},
        )


def test_missing_registry_metadata_is_rejected() -> None:
    registry = load_jurisprudence_metadata(
        Path("jurisprudence/fixtures/metadata_synthetic.jsonl")
    )
    fake = FakeRetriever(raw_result(["missing-document"]))
    service = JurisprudenceRetriever(fake, registry)
    with pytest.raises(JurisprudenceRetrievalError):
        service.search(
            "consulta",
            activation=activated(),
            query_date=date(2026, 8, 28),
            applicable_normative_refs=set(),
        )


@pytest.mark.parametrize("top_k", [0, 21])
def test_top_k_is_bounded(top_k: int) -> None:
    registry = load_jurisprudence_metadata(
        Path("jurisprudence/fixtures/metadata_synthetic.jsonl")
    )
    service = JurisprudenceRetriever(FakeRetriever(raw_result([])), registry)
    with pytest.raises(JurisprudenceRetrievalError):
        service.search(
            "consulta",
            activation=activated(),
            query_date=date(2026, 8, 28),
            applicable_normative_refs=set(),
            top_k=top_k,
        )
