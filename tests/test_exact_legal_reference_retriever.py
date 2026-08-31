from app.domain.chunks import ChunkMetadata, LegalChunk, LegalChunkType, LegalHierarchy
from app.domain.documents import SourceType
from rag.retrieval.lexical_cpu import CpuLexicalRetriever
from rag.retrieval.retriever import FaissRetriever


def _chunk(article: str, index: int) -> LegalChunk:
    return LegalChunk(
        chunk_id=f"cff:article:articulo-{article.lower()}:test-{index}",
        text=f"Artículo {article}. Texto de prueba.",
        metadata=ChunkMetadata(
            document_id="cff",
            canonical_id="cff",
            source_type=SourceType.NORMATIVA,
            source_filename="cff.md",
            chunk_index=index,
            chunk_type=LegalChunkType.ARTICLE,
            legal_identifier=f"Artículo {article}",
            hierarchy=LegalHierarchy(article=f"Artículo {article}"),
            source_sha256="a" * 64,
        ),
    )


def test_faiss_exact_legal_reference_does_not_confuse_27_with_127_or_227() -> None:
    retriever = object.__new__(FaissRetriever)
    retriever._chunks = [_chunk("127", 0), _chunk("27", 1), _chunk("227", 2)]

    result = retriever.find_exact_legal_reference(
        document_id="cff",
        legal_identifier="Artículo 27",
        top_k=5,
    )

    assert result.returned_count == 1
    assert result.hits[0].metadata.legal_identifier == "Artículo 27"
    assert result.hits[0].metadata.document_id == "cff"
    assert result.hits[0].score == 1.0


def test_cpu_exact_legal_reference_does_not_confuse_27_with_127_or_227() -> None:
    retriever = object.__new__(CpuLexicalRetriever)
    retriever._chunks = [_chunk("127", 0), _chunk("27", 1), _chunk("227", 2)]

    result = retriever.find_exact_legal_reference(
        document_id="cff",
        legal_identifier="Artículo 27",
        top_k=5,
    )

    assert result.returned_count == 1
    assert result.hits[0].metadata.legal_identifier == "Artículo 27"
    assert result.hits[0].metadata.document_id == "cff"
    assert result.hits[0].score == 1.0
