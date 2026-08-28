import pytest

from app.domain.chunks import ChunkMetadata, LegalChunkType, LegalHierarchy
from app.domain.documents import SourceType
from llm.errors import LLMResponseValidationError
from llm.models import LLMGenerationContext
from llm.providers.mock import MockLLMProvider
from llm.service import LlamaRAGService
from rag.retrieval.models import RetrievalHit, RetrievalResult


def retrieval_with_hit() -> RetrievalResult:
    metadata = ChunkMetadata(
        document_id="doc-001",
        source_type=SourceType.NORMATIVA,
        source_filename="ley.pdf",
        chunk_index=0,
        chunk_type=LegalChunkType.ARTICLE,
        legal_identifier="1",
        page_start=1,
        page_end=1,
        hierarchy=LegalHierarchy(article="1"),
        source_sha256="a" * 64,
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
                score=0.91,
                chunk_id="chunk-0001",
                text="Texto normativo de prueba.",
                metadata=metadata,
            )
        ],
    )


def test_service_generates_structured_answer_with_mock() -> None:
    result = LlamaRAGService(MockLLMProvider()).explain(retrieval_with_hit())

    assert result.generation_performed is True
    assert result.retrieved_count == 1
    assert result.answer.evidence_ids == ["chunk-0001"]


def test_service_abstains_without_evidence() -> None:
    retrieval = RetrievalResult(
        query="Consulta sin evidencia",
        requested_top_k=5,
        candidate_count=0,
        returned_count=0,
        hits=[],
    )

    result = LlamaRAGService(MockLLMProvider()).explain(retrieval)

    assert result.generation_performed is False
    assert result.answer.requires_human_review is True
    assert result.answer.evidence_ids == []


class HallucinatingProvider:
    @property
    def provider_name(self) -> str:
        return "bad"

    @property
    def model_name(self) -> str:
        return "bad-model"

    def generate_json(
        self,
        context: LLMGenerationContext,
        *,
        response_schema: dict[str, object],
    ) -> str:
        del context, response_schema
        return (
            '{"summary":"s","analysis":"a",'
            '"evidence_ids":["chunk-inventado"],'
            '"uncertainties":[],"requires_human_review":false}'
        )


def test_service_rejects_citation_not_present_in_retrieval() -> None:
    with pytest.raises(LLMResponseValidationError, match="no recuperada"):
        LlamaRAGService(HallucinatingProvider()).explain(retrieval_with_hit())
