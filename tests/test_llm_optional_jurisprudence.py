import pytest

from app.domain.chunks import ChunkMetadata, LegalChunkType, LegalHierarchy
from app.domain.documents import SourceType
from llm.context import build_controlled_legal_context
from llm.models import ExplanationMode
from llm.providers.mock import MockLLMProvider
from llm.service import LlamaRAGService
from rag.retrieval.models import RetrievalHit, RetrievalResult
from tests.test_llm_service import retrieval_with_hit


def jurisprudence_retrieval(
    *,
    source_type: SourceType = SourceType.JURISPRUDENCIA,
) -> RetrievalResult:
    metadata = ChunkMetadata(
        document_id="juris-doc-001",
        source_type=source_type,
        source_filename="jurisprudencia_usuario.pdf",
        chunk_index=0,
        chunk_type=LegalChunkType.DOCUMENT,
        legal_identifier="Tesis opcional 001",
        page_start=3,
        page_end=3,
        hierarchy=LegalHierarchy(),
        source_sha256="b" * 64,
        fiscal_year=2026,
    )
    return RetrievalResult(
        query="¿Qué obligación existe?",
        requested_top_k=5,
        candidate_count=1,
        returned_count=1,
        hits=[
            RetrievalHit(
                rank=1,
                score=0.88,
                chunk_id="juris-chunk-0001",
                text="Criterio jurisprudencial aportado por el usuario.",
                metadata=metadata,
            )
        ],
    )


def test_context_works_without_optional_jurisprudence() -> None:
    context = build_controlled_legal_context(retrieval_with_hit())

    assert [item.chunk_id for item in context.evidence] == ["chunk-0001"]
    assert context.deterministic_evidence is not None
    assert context.deterministic_evidence.jurisprudential_criteria == []


def test_optional_jurisprudence_is_added_as_separate_evidence() -> None:
    context = build_controlled_legal_context(
        retrieval_with_hit(),
        jurisprudence_retrieval=jurisprudence_retrieval(),
    )

    assert [item.chunk_id for item in context.evidence] == [
        "chunk-0001",
        "juris-chunk-0001",
    ]
    assert context.evidence[0].source_type == SourceType.NORMATIVA
    assert context.evidence[1].source_type == SourceType.JURISPRUDENCIA
    assert context.deterministic_evidence is not None
    assert context.deterministic_evidence.normative_evidence_refs == ["chunk-0001"]
    assert context.deterministic_evidence.jurisprudential_criteria == [
        "juris-chunk-0001"
    ]


def test_optional_jurisprudence_does_not_become_normative_evidence() -> None:
    context = build_controlled_legal_context(
        retrieval_with_hit(),
        jurisprudence_retrieval=jurisprudence_retrieval(),
    )

    assert context.deterministic_evidence is not None
    assert "juris-chunk-0001" not in (
        context.deterministic_evidence.normative_evidence_refs
    )
    assert "juris-chunk-0001" not in (
        context.deterministic_evidence.applicable_normative_refs
    )


def test_optional_jurisprudence_rejects_misclassified_document() -> None:
    wrong = jurisprudence_retrieval(source_type=SourceType.NORMATIVA)

    with pytest.raises(ValueError, match="no está clasificada como jurisprudencia"):
        build_controlled_legal_context(
            retrieval_with_hit(),
            jurisprudence_retrieval=wrong,
        )


def test_explanation_mode_does_not_change_jurisprudential_evidence() -> None:
    student = build_controlled_legal_context(
        retrieval_with_hit(),
        explanation_mode=ExplanationMode.STUDENT,
        jurisprudence_retrieval=jurisprudence_retrieval(),
    )
    professional = build_controlled_legal_context(
        retrieval_with_hit(),
        explanation_mode=ExplanationMode.PROFESSIONAL,
        jurisprudence_retrieval=jurisprudence_retrieval(),
    )

    assert student.evidence == professional.evidence
    assert student.deterministic_evidence == professional.deterministic_evidence


def test_llama_service_can_consume_optional_jurisprudence() -> None:
    result = LlamaRAGService(MockLLMProvider()).explain(
        retrieval_with_hit(),
        jurisprudence_retrieval=jurisprudence_retrieval(),
    )

    assert result.generation_performed is True
    assert result.retrieved_count == 2
    assert result.answer.evidence_ids == [
        "chunk-0001",
        "juris-chunk-0001",
    ]
