import json

import pytest

from app.domain.chunks import ChunkMetadata, LegalChunkType, LegalHierarchy
from app.domain.documents import SourceType
from llm.errors import LLMGenerationError, LLMResponseValidationError
from llm.models import DeterministicEvidence, LLMGenerationContext
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


class StaticProvider:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    @property
    def provider_name(self) -> str:
        return "static"

    @property
    def model_name(self) -> str:
        return "static-model"

    def generate_json(
        self,
        context: LLMGenerationContext,
        *,
        response_schema: dict[str, object],
    ) -> str:
        del context, response_schema
        return json.dumps(self._payload, ensure_ascii=False)


class ExplodingProvider:
    @property
    def provider_name(self) -> str:
        return "exploding"

    @property
    def model_name(self) -> str:
        return "exploding-model"

    def generate_json(
        self,
        context: LLMGenerationContext,
        *,
        response_schema: dict[str, object],
    ) -> str:
        del context, response_schema
        raise RuntimeError("provider unavailable")


def valid_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "summary": "Resumen fundado.",
        "analysis": "Análisis basado en la evidencia autorizada.",
        "evidence_ids": ["chunk-0001"],
        "uncertainties": [],
        "requires_human_review": False,
    }
    payload.update(overrides)
    return payload


def test_service_rejects_citation_not_present_in_retrieval() -> None:
    provider = StaticProvider(
        valid_payload(evidence_ids=["chunk-inventado"])
    )

    with pytest.raises(LLMResponseValidationError, match="no recuperada"):
        LlamaRAGService(provider).explain(retrieval_with_hit())


def test_service_rejects_invalid_structured_output() -> None:
    provider = StaticProvider({"summary": "incompleto"})

    with pytest.raises(LLMResponseValidationError, match="contrato JSON"):
        LlamaRAGService(provider).explain(retrieval_with_hit())


def test_service_wraps_unexpected_provider_failure() -> None:
    with pytest.raises(LLMGenerationError, match="falló de forma controlada"):
        LlamaRAGService(ExplodingProvider()).explain(retrieval_with_hit())


def test_llm_cannot_clear_deterministic_human_review() -> None:
    provider = StaticProvider(valid_payload(requires_human_review=False))
    deterministic = DeterministicEvidence(requires_human_review=True)

    with pytest.raises(
        LLMResponseValidationError,
        match="no puede eliminar una revisión humana",
    ):
        LlamaRAGService(provider).explain(
            retrieval_with_hit(),
            deterministic_evidence=deterministic,
        )


def test_llm_may_preserve_deterministic_human_review() -> None:
    provider = StaticProvider(valid_payload(requires_human_review=True))
    deterministic = DeterministicEvidence(requires_human_review=True)

    result = LlamaRAGService(provider).explain(
        retrieval_with_hit(),
        deterministic_evidence=deterministic,
    )

    assert result.answer.requires_human_review is True


def test_context_copies_deterministic_evidence_before_enrichment() -> None:
    deterministic = DeterministicEvidence(
        applicable_normative_refs=["NORM-001"],
        rule_conclusions=["RULE-001"],
        calculations=["ISR=2300.00"],
        similar_cases=["CASE-001"],
    )

    context = LlamaRAGService._context_from_retrieval(
        retrieval_with_hit(),
        deterministic_evidence=deterministic,
    )

    assert context.deterministic_evidence is not deterministic
    assert context.deterministic_evidence is not None
    assert context.deterministic_evidence.applicable_normative_refs == ["NORM-001"]
    assert context.deterministic_evidence.rule_conclusions == ["RULE-001"]
    assert context.deterministic_evidence.calculations == ["ISR=2300.00"]
    assert context.deterministic_evidence.similar_cases == ["CASE-001"]
    assert context.deterministic_evidence.normative_evidence_refs == ["chunk-0001"]

    # Enrichment must not mutate the caller-owned deterministic object.
    assert deterministic.normative_evidence_refs == []
