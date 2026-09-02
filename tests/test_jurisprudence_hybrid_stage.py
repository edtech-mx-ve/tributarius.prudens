from app.domain.jurisprudence import JurisprudenceStatus, NormRelationType
from app.domain.jurisprudence_document import (
    JurisprudenceDocumentRepresentation,
    JurisprudencePage,
)
from app.domain.jurisprudence_extraction import JurisprudenceExtractedMetadata
from app.services.jurisprudence_hybrid_stage import run_session_jurisprudence_stage

SHA = "a" * 64


def _document() -> JurisprudenceDocumentRepresentation:
    text = "Devolución de saldo a favor conforme al artículo 22 del CFF."
    return JurisprudenceDocumentRepresentation(
        document_id="jurisprudencia-test",
        original_filename="criterio.pdf",
        source_sha256=SHA,
        page_count=1,
        extracted_characters=len(text),
        pages=[JurisprudencePage(number=1, text=text, has_extractable_text=True)],
        full_text=text,
    )


def _metadata() -> JurisprudenceExtractedMetadata:
    return JurisprudenceExtractedMetadata(
        identifier="20260001",
        title="DEVOLUCIÓN DE SALDO A FAVOR.",
        court_or_body="Primera Sala",
        status=JurisprudenceStatus.UNKNOWN,
        matter="fiscal",
        related_normative_refs=["CFF:22"],
        relation_type=NormRelationType.INTERPRETS,
        source_pages=[1],
        requires_human_review=True,
    )


def test_session_hybrid_stage_preserves_retrieval_and_relations() -> None:
    result = run_session_jurisprudence_stage(
        query="devolución saldo favor artículo 22",
        documents=[_document()],
        metadata_by_document_id={"jurisprudencia-test": _metadata()},
        applicable_normative_refs={"CFF:22"},
        matter="fiscal",
        top_k=5,
    )

    assert result.retrieval.returned_count == 1
    assert len(result.applicability) == 1
    assert result.applicability[0].applicable_candidate is True
    assert result.relations.concordant_count == 1
    assert result.evidence
    assert result.requires_human_review is True


def test_session_hybrid_stage_does_not_promote_unrelated_norm() -> None:
    result = run_session_jurisprudence_stage(
        query="devolución saldo favor artículo 22",
        documents=[_document()],
        metadata_by_document_id={"jurisprudencia-test": _metadata()},
        applicable_normative_refs={"CFF:28"},
        matter="fiscal",
        top_k=5,
    )

    assert result.applicability[0].applicable_candidate is False
    assert result.relations.concordant_count == 0
    assert result.relations.distinguishable_count == 1
    assert result.evidence == []


def test_session_hybrid_stage_skips_hit_without_metadata() -> None:
    result = run_session_jurisprudence_stage(
        query="devolución saldo favor artículo 22",
        documents=[_document()],
        metadata_by_document_id={},
        applicable_normative_refs={"CFF:22"},
        matter="fiscal",
        top_k=5,
    )

    assert result.retrieval.returned_count == 1
    assert result.applicability == []
    assert result.evidence == []
