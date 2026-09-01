from app.domain.chunks import ChunkMetadata, LegalChunkType, LegalHierarchy
from app.domain.documents import SourceType
from app.domain.orchestration import classify_retrieval_evidence
from rag.retrieval.models import RetrievalHit, RetrievalResult


def _hit(rank: int, source_type: SourceType, chunk_id: str) -> RetrievalHit:
    return RetrievalHit(
        rank=rank,
        score=0.9,
        chunk_id=chunk_id,
        text="Evidencia de prueba.",
        metadata=ChunkMetadata(
            document_id=f"doc-{rank}",
            source_type=source_type,
            source_filename=f"doc-{rank}.md",
            chunk_index=rank - 1,
            chunk_type=LegalChunkType.SECTION,
            hierarchy=LegalHierarchy(),
            source_sha256=str(rank) * 64,
        ),
    )


def test_classifies_prodecon_and_unam_without_mixing_normativa() -> None:
    retrieval = RetrievalResult(
        query="derechos del contribuyente",
        requested_top_k=3,
        candidate_count=3,
        returned_count=3,
        hits=[
            _hit(1, SourceType.PRODECON, "prodecon-07"),
            _hit(2, SourceType.UNAM, "unam-capitulo-i"),
            _hit(3, SourceType.NORMATIVA, "lfdc-articulo-2"),
        ],
    )

    prodecon_refs, unam_refs = classify_retrieval_evidence(retrieval)

    assert prodecon_refs == ["prodecon-07"]
    assert unam_refs == ["unam-capitulo-i"]
    assert "lfdc-articulo-2" not in prodecon_refs
    assert "lfdc-articulo-2" not in unam_refs


def test_preserves_multiple_refs_per_complementary_layer() -> None:
    retrieval = RetrievalResult(
        query="interpretacion fiscal",
        requested_top_k=4,
        candidate_count=4,
        returned_count=4,
        hits=[
            _hit(1, SourceType.PRODECON, "prodecon-09-a"),
            _hit(2, SourceType.PRODECON, "prodecon-09-b"),
            _hit(3, SourceType.UNAM, "unam-capitulo-ii-a"),
            _hit(4, SourceType.UNAM, "unam-capitulo-ii-b"),
        ],
    )

    prodecon_refs, unam_refs = classify_retrieval_evidence(retrieval)

    assert prodecon_refs == ["prodecon-09-a", "prodecon-09-b"]
    assert unam_refs == ["unam-capitulo-ii-a", "unam-capitulo-ii-b"]
