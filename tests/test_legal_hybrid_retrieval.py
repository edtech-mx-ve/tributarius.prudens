from __future__ import annotations

from collections.abc import Iterable

from app.domain.chunks import ChunkMetadata, LegalChunkType, LegalHierarchy
from app.domain.documents import SourceType
from rag.retrieval.filters import RetrievalFilters
from rag.retrieval.legal_hybrid import (
    LegalHybridRetriever,
    LegalRetrievalPolicy,
    classify_query_mode,
    route_documents,
)
from rag.retrieval.models import RetrievalHit, RetrievalResult


def _hit(
    rank: int,
    score: float,
    document_id: str,
    *,
    text: str,
    source_type: SourceType = SourceType.NORMATIVA,
    source_role: str = "ley",
) -> RetrievalHit:
    return RetrievalHit(
        rank=rank,
        score=score,
        chunk_id=f"{document_id}-{rank:03d}",
        text=text,
        metadata=ChunkMetadata(
            document_id=document_id,
            source_type=source_type,
            source_filename=f"{document_id}.md",
            chunk_index=rank - 1,
            chunk_type=LegalChunkType.ARTICLE,
            hierarchy=LegalHierarchy(),
            source_sha256="a" * 64,
            source_role=source_role,
            title=document_id,
        ),
    )


class FakeRetriever:
    def __init__(self, hits: Iterable[RetrievalHit]) -> None:
        self.hits = list(hits)
        self.calls: list[tuple[int, set[str]]] = []

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> RetrievalResult:
        document_ids = set(filters.document_ids) if filters else set()
        self.calls.append((top_k, document_ids))
        eligible = [
            hit
            for hit in self.hits
            if not document_ids or hit.metadata.document_id in document_ids
        ]
        selected = eligible[:top_k]
        normalized = [
            hit.model_copy(update={"rank": rank})
            for rank, hit in enumerate(selected, start=1)
        ]
        return RetrievalResult(
            query=query,
            requested_top_k=top_k,
            candidate_count=len(eligible),
            returned_count=len(normalized),
            hits=normalized,
        )


def _policy() -> LegalRetrievalPolicy:
    return LegalRetrievalPolicy.model_validate(
        {
            "candidate_pool": 10,
            "target_candidates": 2,
            "max_hits_per_document": 3,
            "weights": {
                "lexical": 0.10,
                "route": 0.15,
                "authority": 0.05,
                "doctrine": 0.08,
            },
            "authority_by_role": {
                "constitucional": 1.0,
                "ley": 0.95,
                "doctrina": 0.40,
            },
            "doctrinal_markers": [
                "como se interpreta",
                "metodos de interpretacion",
            ],
            "normative_markers": [
                "ley",
                "constitucionales",
                "impuesto",
                "tasa",
            ],
            "document_routes": [
                {
                    "document_id": "liva",
                    "aliases": ["iva", "valor agregado"],
                },
                {
                    "document_id": "cpeum",
                    "aliases": ["constitucionales", "proporcionalidad equidad"],
                },
                {
                    "document_id": "manual_derecho_fiscal_unam",
                    "aliases": ["metodos de interpretacion"],
                    "modes": ["doctrinal"],
                },
            ],
        }
    )


def test_router_distinguishes_normative_and_doctrinal_queries() -> None:
    policy = _policy()

    assert classify_query_mode(
        "principios constitucionales proporcionalidad equidad",
        policy,
    ) == "normative"
    assert classify_query_mode(
        "cómo se interpreta y métodos de interpretación fiscal",
        policy,
    ) == "doctrinal"

    routed = route_documents(
        "Ley del IVA tasa general al valor agregado",
        "normative",
        policy,
    )
    assert "liva" in routed


def test_reranker_promotes_routed_primary_law() -> None:
    hits = [
        _hit(
            1,
            0.82,
            "manual_derecho_fiscal_unam",
            text="La tasa general del IVA es 16 por ciento.",
            source_type=SourceType.UNAM,
            source_role="doctrina",
        ),
        _hit(
            2,
            0.76,
            "rmf_2026",
            text="Regla administrativa relacionada con IVA.",
            source_role="regla_administrativa",
        ),
        _hit(
            3,
            0.74,
            "liva",
            text="Ley del Impuesto al Valor Agregado. Tasa general.",
        ),
    ]
    retriever = LegalHybridRetriever(FakeRetriever(hits), _policy())

    result = retriever.search(
        "Ley del IVA tasa general impuesto al valor agregado",
        top_k=3,
    )

    assert result.hits[0].metadata.document_id == "liva"


def test_missing_routed_document_is_enriched_with_filtered_search() -> None:
    all_hits = [
        _hit(
            1,
            0.86,
            "manual_derecho_fiscal_unam",
            text="Principios constitucionales tributarios.",
            source_type=SourceType.UNAM,
            source_role="doctrina",
        ),
        _hit(
            2,
            0.72,
            "cpeum",
            text="Contribuir de manera proporcional y equitativa.",
            source_role="constitucional",
        ),
    ]

    class MissingFromBroadFake(FakeRetriever):
        def search(
            self,
            query: str,
            *,
            top_k: int = 5,
            filters: RetrievalFilters | None = None,
        ) -> RetrievalResult:
            document_ids = set(filters.document_ids) if filters else set()
            self.calls.append((top_k, document_ids))
            if not document_ids:
                eligible = [self.hits[0]]
            else:
                eligible = [
                    hit
                    for hit in self.hits
                    if hit.metadata.document_id in document_ids
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

    fake = MissingFromBroadFake(all_hits)
    retriever = LegalHybridRetriever(fake, _policy())

    traced = retriever.search_with_trace(
        "principios constitucionales proporcionalidad equidad contribuciones",
        top_k=2,
    )

    assert traced.enriched_candidate_count == 1
    assert "cpeum" in traced.routed_document_ids
    assert traced.result.hits[0].metadata.document_id == "cpeum"
    assert any(document_ids == {"cpeum"} for _k, document_ids in fake.calls)


def test_doctrinal_query_does_not_apply_normative_authority_bonus() -> None:
    hits = [
        _hit(
            1,
            0.80,
            "manual_derecho_fiscal_unam",
            text="Métodos de interpretación fiscal.",
            source_type=SourceType.UNAM,
            source_role="doctrina",
        ),
        _hit(
            2,
            0.79,
            "cff",
            text="Código Fiscal de la Federación.",
            source_role="ley",
        ),
    ]
    retriever = LegalHybridRetriever(FakeRetriever(hits), _policy())

    traced = retriever.search_with_trace(
        "cómo se interpreta una norma y métodos de interpretación fiscal",
        top_k=2,
    )

    first = traced.result.hits[0]
    assert traced.query_mode == "doctrinal"
    assert first.metadata.document_id == "manual_derecho_fiscal_unam"
    trace = traced.traces[first.chunk_id]
    assert "doctrinal_fit" in trace.reasons
    assert "legal_authority" not in trace.reasons


def test_diversity_cap_limits_document_monopoly() -> None:
    hits = [
        _hit(i, 0.90 - i * 0.01, "cff", text="RFC obligación fiscal.")
        for i in range(1, 6)
    ] + [
        _hit(6, 0.75, "lfdc", text="Derechos del contribuyente.")
    ]
    policy = _policy().model_copy(update={"max_hits_per_document": 2})
    retriever = LegalHybridRetriever(FakeRetriever(hits), policy)

    result = retriever.search("obligación fiscal RFC", top_k=3)

    assert [hit.metadata.document_id for hit in result.hits].count("cff") == 2
    assert "lfdc" in [hit.metadata.document_id for hit in result.hits]


def test_routed_document_is_enriched_even_when_weakly_present_in_broad_pool() -> None:
    broad_route_hit = _hit(
        1,
        0.40,
        "liva",
        text="Referencia incidental al IVA.",
    )
    strong_target_hit = _hit(
        2,
        0.91,
        "liva",
        text="Ley del Impuesto al Valor Agregado. Tasa general.",
    )
    distractor = _hit(
        3,
        0.88,
        "rmf_2026",
        text="Regla administrativa relacionada.",
        source_role="regla_administrativa",
    )

    class WeakBroadFake(FakeRetriever):
        def search(
            self,
            query: str,
            *,
            top_k: int = 5,
            filters: RetrievalFilters | None = None,
        ) -> RetrievalResult:
            document_ids = set(filters.document_ids) if filters else set()
            self.calls.append((top_k, document_ids))
            if document_ids == {"liva"}:
                eligible = [strong_target_hit]
            else:
                eligible = [broad_route_hit, distractor]
            return RetrievalResult(
                query=query,
                requested_top_k=top_k,
                candidate_count=len(eligible),
                returned_count=len(eligible[:top_k]),
                hits=[
                    hit.model_copy(update={"rank": rank})
                    for rank, hit in enumerate(eligible[:top_k], start=1)
                ],
            )

    fake = WeakBroadFake([broad_route_hit, strong_target_hit, distractor])
    retriever = LegalHybridRetriever(fake, _policy())

    traced = retriever.search_with_trace(
        "Ley del IVA tasa general",
        top_k=2,
    )

    assert any(document_ids == {"liva"} for _k, document_ids in fake.calls)
    assert traced.enriched_candidate_count == 1
    assert traced.result.hits[0].metadata.document_id == "liva"


def test_public_score_is_clamped_but_trace_preserves_composite_score() -> None:
    hits = [
        _hit(
            1,
            0.99,
            "cpeum",
            text="Principios constitucionales proporcionalidad equidad.",
            source_role="constitucional",
        )
    ]
    retriever = LegalHybridRetriever(FakeRetriever(hits), _policy())

    traced = retriever.search_with_trace(
        "principios constitucionales proporcionalidad equidad",
        top_k=1,
    )

    public_hit = traced.result.hits[0]
    trace = traced.traces[public_hit.chunk_id]
    assert public_hit.score == 1.0
    assert trace.final_score > 1.0


def test_explicit_routed_document_is_kept_in_top_k_coverage() -> None:
    distractors = [
        _hit(
            rank,
            0.95 - rank * 0.01,
            f"other_{rank}",
            text="Fundamento legal administrativo general.",
        )
        for rank in range(1, 6)
    ]
    routed = _hit(
        6,
        0.10,
        "liva",
        text="Ley del Impuesto al Valor Agregado.",
    )

    class CoverageFake(FakeRetriever):
        def search(
            self,
            query: str,
            *,
            top_k: int = 5,
            filters: RetrievalFilters | None = None,
        ) -> RetrievalResult:
            document_ids = set(filters.document_ids) if filters else set()
            self.calls.append((top_k, document_ids))
            if document_ids == {"liva"}:
                eligible = [routed]
            else:
                eligible = [*distractors, routed]
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

    retriever = LegalHybridRetriever(
        CoverageFake([*distractors, routed]),
        _policy(),
    )
    result = retriever.search(
        "Ley del IVA y su fundamento legal",
        top_k=5,
    )

    assert "liva" in [hit.metadata.document_id for hit in result.hits]
