import pytest

from app.domain.jurisprudence_document import (
    JurisprudenceDocumentRepresentation,
    JurisprudencePage,
)
from jurisprudence.retrieval import (
    JurisprudenceRetrievalError,
    SessionJurisprudenceRetriever,
)

SHA_A = "a" * 64
SHA_B = "b" * 64


def _document(
    document_id: str,
    sha256: str,
    pages: list[str],
) -> JurisprudenceDocumentRepresentation:
    jurisprudence_pages = [
        JurisprudencePage(
            number=index,
            text=text,
            has_extractable_text=bool(text),
        )
        for index, text in enumerate(pages, start=1)
    ]
    full_text = "\n\n".join(text for text in pages if text)
    return JurisprudenceDocumentRepresentation(
        document_id=document_id,
        original_filename=f"{document_id}.pdf",
        source_sha256=sha256,
        page_count=len(jurisprudence_pages),
        extracted_characters=len(full_text),
        pages=jurisprudence_pages,
        full_text=full_text,
    )


def test_session_retrieval_ranks_relevant_pages_deterministically() -> None:
    retriever = SessionJurisprudenceRetriever(
        [
            _document(
                "jurisprudencia-b",
                SHA_B,
                ["IVA acreditamiento devolución.", "Tema distinto."],
            ),
            _document(
                "jurisprudencia-a",
                SHA_A,
                ["IVA devolución saldo a favor acreditamiento.", "ISR deducciones."],
            ),
        ]
    )

    result = retriever.search("IVA devolución acreditamiento", top_k=3)

    assert result.returned_count == 2
    assert result.hits[0].document_id == "jurisprudencia-a"
    assert result.hits[0].page_number == 1
    assert result.hits[0].score == 1.0
    assert result.hits[1].document_id == "jurisprudencia-b"
    assert [hit.rank for hit in result.hits] == [1, 2]


def test_session_retrieval_is_accent_insensitive() -> None:
    retriever = SessionJurisprudenceRetriever(
        [_document("jurisprudencia-a", SHA_A, ["Devolución y compensación fiscal."])]
    )

    result = retriever.search("devolucion compensacion")

    assert result.returned_count == 1
    assert result.hits[0].score == 1.0


def test_session_retrieval_preserves_provenance() -> None:
    retriever = SessionJurisprudenceRetriever(
        [_document("jurisprudencia-a", SHA_A, ["Artículo 22 devolución."])]
    )

    hit = retriever.search("artículo 22").hits[0]

    assert hit.original_filename == "jurisprudencia-a.pdf"
    assert hit.source_sha256 == SHA_A
    assert hit.page_number == 1


def test_session_retrieval_ignores_empty_and_unrelated_pages() -> None:
    retriever = SessionJurisprudenceRetriever(
        [_document("jurisprudencia-a", SHA_A, ["", "Materia laboral sin relación."])]
    )

    result = retriever.search("devolución fiscal")

    assert result.candidate_count == 0
    assert result.returned_count == 0
    assert result.hits == []


def test_session_retrieval_respects_minimum_score() -> None:
    retriever = SessionJurisprudenceRetriever(
        [_document("jurisprudencia-a", SHA_A, ["IVA devolución."])]
    )

    result = retriever.search(
        "IVA devolución acreditamiento",
        minimum_score=0.8,
    )

    assert result.returned_count == 0


@pytest.mark.parametrize("query", ["", "   "])
def test_session_retrieval_rejects_empty_query(query: str) -> None:
    retriever = SessionJurisprudenceRetriever(
        [_document("jurisprudencia-a", SHA_A, ["IVA devolución."])]
    )

    with pytest.raises(JurisprudenceRetrievalError, match="consulta no puede"):
        retriever.search(query)


def test_session_retrieval_rejects_duplicate_documents() -> None:
    document = _document("jurisprudencia-a", SHA_A, ["IVA devolución."])

    with pytest.raises(JurisprudenceRetrievalError, match="no pueden repetirse"):
        SessionJurisprudenceRetriever([document, document])
