from __future__ import annotations

from collections.abc import Iterable

from app.domain.chunks import (
    ChunkMetadata,
    LegalChunk,
    LegalChunkType,
    LegalHierarchy,
)
from app.domain.documents import SourceType
from rag.retrieval.filters import RetrievalFilters
from rag.retrieval.legal_hybrid import (
    LegalHybridRetriever,
    extract_article_identifier,
    normalize_search_text,
)
from rag.retrieval.lexical_cpu import CpuLexicalRetriever
from rag.retrieval.models import RetrievalHit, RetrievalResult
from rag.retrieval.retriever import FaissRetriever


def _chunk(document_id: str, article: str, index: int) -> LegalChunk:
    return LegalChunk(
        chunk_id=f"{document_id}:article:test-{index}",
        text=f"Artículo {article}. Texto de prueba.",
        metadata=ChunkMetadata(
            document_id=document_id,
            canonical_id=document_id,
            source_type=SourceType.NORMATIVA,
            source_filename=f"{document_id}.md",
            chunk_index=index,
            chunk_type=LegalChunkType.ARTICLE,
            legal_identifier=f"Artículo {article}",
            hierarchy=LegalHierarchy(article=f"Artículo {article}"),
            source_sha256="a" * 64,
            source_role="ley",
        ),
    )


def _hit(
    rank: int,
    score: float,
    document_id: str,
    article: str | None,
    text: str,
    *,
    source_role: str = "ley",
) -> RetrievalHit:
    return RetrievalHit(
        rank=rank,
        score=score,
        chunk_id=f"{document_id}-{rank}",
        text=text,
        metadata=ChunkMetadata(
            document_id=document_id,
            canonical_id=document_id,
            source_type=SourceType.NORMATIVA,
            source_filename=f"{document_id}.md",
            chunk_index=rank - 1,
            chunk_type=LegalChunkType.ARTICLE,
            legal_identifier=article,
            hierarchy=LegalHierarchy(article=article),
            source_sha256="a" * 64,
            source_role=source_role,
        ),
    )


class FakeRetriever:
    def __init__(self, hits: Iterable[RetrievalHit]) -> None:
        self.hits = list(hits)

    def find_exact_legal_reference(
        self,
        *,
        document_id: str,
        legal_identifier: str,
        top_k: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> RetrievalResult:
        wanted = normalize_search_text(legal_identifier)
        eligible = [
            hit
            for hit in self.hits
            if hit.metadata.document_id == document_id
            and hit.metadata.legal_identifier is not None
            and normalize_search_text(hit.metadata.legal_identifier) == wanted
        ][:top_k]
        return RetrievalResult(
            query=legal_identifier,
            requested_top_k=top_k,
            candidate_count=len(eligible),
            returned_count=len(eligible),
            hits=[
                hit.model_copy(update={"rank": rank})
                for rank, hit in enumerate(eligible, start=1)
            ],
        )

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> RetrievalResult:
        document_ids = set(filters.document_ids) if filters else set()
        eligible = [
            hit
            for hit in self.hits
            if not document_ids or hit.metadata.document_id in document_ids
        ]
        selected = eligible[:top_k]
        return RetrievalResult(
            query=query,
            requested_top_k=top_k,
            candidate_count=len(eligible),
            returned_count=len(selected),
            hits=[
                hit.model_copy(update={"rank": rank})
                for rank, hit in enumerate(selected, start=1)
            ],
        )


def test_extract_article_identifier_supports_compound_legal_forms() -> None:
    cases = {
        "artículo 27 del CFF": "Artículo 27",
        "CFF art. 32-B": "Artículo 32-B",
        "artículo 1o.-A del IVA": "Artículo 1o-A",
        "artículo 1o-A BIS del IVA": "Artículo 1o-A BIS",
        "ARTÍCULO 6o. Bis del juicio contencioso": "Artículo 6o BIS",
        "CFF art. 32-B BIS": "Artículo 32-B BIS",
        "CFF art. 32-B TER": "Artículo 32-B TER",
    }
    for query, expected in cases.items():
        assert extract_article_identifier(query) == expected


def _assert_exact_cases(
    retriever: FaissRetriever | CpuLexicalRetriever,
) -> None:
    cases = [
        ("cpeum", "31", ["131", "31", "231"]),
        ("liva", "1o-A", ["1o", "1o-A", "1o-B"]),
        ("lfpca", "6o Bis", ["6o", "6o Bis", "7o Bis"]),
        ("cff", "32-B BIS", ["32-B", "32-B BIS", "32-B TER"]),
    ]

    for document_id, target, articles in cases:
        retriever._chunks = [
            _chunk(document_id, article, index)
            for index, article in enumerate(articles)
        ]
        result = retriever.find_exact_legal_reference(
            document_id=document_id,
            legal_identifier=f"Artículo {target.upper()}",
            top_k=5,
        )
        assert result.returned_count == 1
        assert result.hits[0].metadata.document_id == document_id
        assert normalize_search_text(
            result.hits[0].metadata.legal_identifier or ""
        ) == normalize_search_text(f"Artículo {target}")
        assert result.hits[0].score == 1.0


def test_low_level_exact_retrievers_cover_multiple_normative_sources() -> None:
    faiss_retriever = object.__new__(FaissRetriever)
    cpu_retriever = object.__new__(CpuLexicalRetriever)

    _assert_exact_cases(faiss_retriever)
    _assert_exact_cases(cpu_retriever)


def test_hybrid_exact_reference_precedes_stronger_semantic_neighbor() -> None:
    policy_path = "app/resources/legal_retrieval_policy.json"
    cases = [
        (
            "¿Qué establece el artículo 31 de la Constitución?",
            "cpeum",
            "Artículo 31",
            "Artículo 131",
            "constitucional",
        ),
        (
            "¿Qué establece el artículo 1o-A del IVA?",
            "liva",
            "Artículo 1o-A",
            "Artículo 1o-B",
            "ley",
        ),
        (
            "¿Qué establece el artículo 6o. Bis del juicio contencioso?",
            "lfpca",
            "Artículo 6o Bis",
            "Artículo 6o",
            "defensa",
        ),
        (
            "¿Qué establece el artículo 32-B BIS del CFF?",
            "cff",
            "Artículo 32-B BIS",
            "Artículo 32-B",
            "ley",
        ),
    ]

    for query, document_id, exact_id, neighbor_id, role in cases:
        hits = [
            _hit(
                1,
                0.99,
                document_id,
                neighbor_id,
                f"{neighbor_id}. Vecino semántico.",
                source_role=role,
            ),
            _hit(
                2,
                0.55,
                document_id,
                exact_id,
                f"{exact_id}. Referencia exacta.",
                source_role=role,
            ),
        ]
        retriever = LegalHybridRetriever.from_policy_file(
            FakeRetriever(hits),
            path=__import__("pathlib").Path(policy_path),
        )
        traced = retriever.search_with_trace(query, top_k=2)
        first = traced.result.hits[0]
        assert first.metadata.document_id == document_id
        assert normalize_search_text(first.metadata.legal_identifier or "") == (
            normalize_search_text(exact_id)
        )
        assert traced.traces[first.chunk_id].exact_legal_reference is True


def test_hybrid_keeps_semantic_complement_after_exact_hit() -> None:
    hits = [
        _hit(
            1,
            0.98,
            "liva",
            "Artículo 1o-B",
            "Artículo 1o-B. Resultado semántico relacionado.",
        ),
        _hit(
            2,
            0.52,
            "liva",
            "Artículo 1o-A",
            "Artículo 1o-A. Referencia exacta.",
        ),
        _hit(
            3,
            0.90,
            "rmf_2026",
            None,
            "Regla administrativa relacionada con IVA.",
            source_role="regla_administrativa",
        ),
    ]
    retriever = LegalHybridRetriever.from_policy_file(
        FakeRetriever(hits),
        path=__import__("pathlib").Path("app/resources/legal_retrieval_policy.json"),
    )

    traced = retriever.search_with_trace(
        "¿Qué establece el artículo 1o-A del IVA?",
        top_k=3,
    )

    identifiers = [
        normalize_search_text(hit.metadata.legal_identifier or "")
        for hit in traced.result.hits
    ]
    assert identifiers[0] == normalize_search_text("Artículo 1o-A")
    assert normalize_search_text("Artículo 1o-B") in identifiers
    assert traced.semantic_candidate_count >= 2
