from __future__ import annotations

from app.domain.chunks import ChunkMetadata, LegalChunkType, LegalHierarchy
from app.domain.documents import SourceType
from app.services.normative_rag_bridge import (
    build_rule_normative_refs,
    stable_legal_ref_from_hit,
)
from rag.retrieval.models import RetrievalHit, RetrievalResult

SHA = "0" * 64


def _hit(
    *,
    chunk_id: str,
    document_id: str,
    unit: str,
    source_type: SourceType = SourceType.NORMATIVA,
) -> RetrievalHit:
    return RetrievalHit(
        rank=1,
        score=1.0,
        chunk_id=chunk_id,
        text=f"{unit}. Texto normativo controlado.",
        metadata=ChunkMetadata(
            document_id=document_id,
            source_type=source_type,
            source_filename=f"{document_id}.md",
            chunk_index=0,
            chunk_type=LegalChunkType.ARTICLE,
            legal_identifier=unit,
            source_unit_label=unit,
            hierarchy=LegalHierarchy(article=unit),
            source_sha256=SHA,
            version_label="test-version",
        ),
    )


def _retrieval(*hits: RetrievalHit) -> RetrievalResult:
    return RetrievalResult(
        query="consulta",
        requested_top_k=5,
        candidate_count=len(hits),
        returned_count=len(hits),
        hits=list(hits),
    )


def test_stable_legal_ref_matches_production_rule_identity() -> None:
    hit = _hit(
        chunk_id="chunk-lisr-110",
        document_id="lisr",
        unit="Artículo 110",
    )

    assert stable_legal_ref_from_hit(hit) == "lisr:articulo_110"


def test_stable_legal_ref_normalizes_ordinal_and_suffix() -> None:
    assert stable_legal_ref_from_hit(
        _hit(chunk_id="c1", document_id="cff", unit="Artículo 1o.")
    ) == "cff:articulo_1"

    assert stable_legal_ref_from_hit(
        _hit(chunk_id="c2", document_id="liva", unit="Artículo 1o.-A")
    ) == "liva:articulo_1_a"

    assert stable_legal_ref_from_hit(
        _hit(chunk_id="c3", document_id="cff", unit="Artículo 6o Bis")
    ) == "cff:articulo_6_bis"


def test_only_applicable_chunks_enable_stable_rule_refs() -> None:
    lisr_110 = _hit(
        chunk_id="chunk-lisr-110",
        document_id="lisr",
        unit="Artículo 110",
    )
    lfdc_2 = _hit(
        chunk_id="chunk-lfdc-2",
        document_id="lfdc",
        unit="Artículo 2o.",
    )
    retrieval = _retrieval(lisr_110, lfdc_2)

    refs = build_rule_normative_refs(
        retrieval,
        {"chunk-lisr-110"},
    )

    assert refs == {
        "chunk-lisr-110",
        "lisr:articulo_110",
    }
    assert "lfdc:articulo_2" not in refs


def test_non_normative_hit_never_becomes_rule_normative_ref() -> None:
    prodecon = _hit(
        chunk_id="chunk-prodecon",
        document_id="prodecon",
        unit="Artículo 2",
        source_type=SourceType.PRODECON,
    )
    retrieval = _retrieval(prodecon)

    refs = build_rule_normative_refs(
        retrieval,
        {"chunk-prodecon"},
    )

    assert refs == {"chunk-prodecon"}
