from app.domain.chunks import LegalChunkType
from app.domain.documents import SourceType
from rag.retrieval.filters import RetrievalFilters


def test_filters_match_normative_fiscal_year() -> None:
    filters = RetrievalFilters(
        source_types={SourceType.NORMATIVA},
        fiscal_year=2026,
    )

    assert filters.matches(
        source_type=SourceType.NORMATIVA,
        chunk_type=LegalChunkType.ARTICLE,
        fiscal_year=2026,
        version_label="2026",
        document_id="doc-1",
    )
    assert not filters.matches(
        source_type=SourceType.JURISPRUDENCIA,
        chunk_type=LegalChunkType.ARTICLE,
        fiscal_year=2026,
        version_label="2026",
        document_id="doc-1",
    )


def test_filters_keep_jurisprudence_separate() -> None:
    filters = RetrievalFilters(source_types={SourceType.JURISPRUDENCIA})

    assert filters.matches(
        source_type=SourceType.JURISPRUDENCIA,
        chunk_type=LegalChunkType.PARAGRAPH,
        fiscal_year=None,
        version_label=None,
        document_id="jur-1",
    )
    assert not filters.matches(
        source_type=SourceType.NORMATIVA,
        chunk_type=LegalChunkType.PARAGRAPH,
        fiscal_year=None,
        version_label=None,
        document_id="norm-1",
    )
