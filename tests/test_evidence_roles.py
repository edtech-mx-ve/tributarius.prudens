from app.domain.chunks import ChunkMetadata, LegalChunkType, LegalHierarchy
from app.domain.documents import SourceType
from app.domain.orchestration import (
    EvidenceRole,
    build_evidence_layers,
)
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


def test_builds_distinct_legal_roles_for_three_evidence_layers() -> None:
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

    layers = build_evidence_layers(
        retrieval,
        normative_evidence_refs=["lfdc-articulo-2"],
    )

    assert [layer.role for layer in layers] == [
        EvidenceRole.ORIENTATIVE,
        EvidenceRole.ACADEMIC_FOUNDATION,
        EvidenceRole.NORMATIVE,
    ]
    assert layers[0].refs == ["prodecon-07"]
    assert layers[1].refs == ["unam-capitulo-i"]
    assert layers[2].refs == ["lfdc-articulo-2"]


def test_prodecon_and_unam_are_never_promoted_to_normative_layer() -> None:
    retrieval = RetrievalResult(
        query="interpretacion fiscal",
        requested_top_k=2,
        candidate_count=2,
        returned_count=2,
        hits=[
            _hit(1, SourceType.PRODECON, "prodecon-09"),
            _hit(2, SourceType.UNAM, "unam-capitulo-ii"),
        ],
    )

    layers = build_evidence_layers(retrieval, normative_evidence_refs=[])

    normative = next(layer for layer in layers if layer.role == EvidenceRole.NORMATIVE)
    assert normative.refs == []
    assert "prodecon-09" not in normative.refs
    assert "unam-capitulo-ii" not in normative.refs
