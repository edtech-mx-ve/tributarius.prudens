from __future__ import annotations

import json

import pytest

from app.domain.chunks import ChunkMetadata, LegalChunkType, LegalHierarchy
from app.domain.documents import SourceType
from app.domain.legal_hypothesis import LegalHypothesisStatus
from app.services.legal_hypothesis_generation import LlamaLegalHypothesisService
from llm.errors import LLMGenerationError, LLMResponseValidationError
from llm.models import LLMGenerationContext
from rag.retrieval.models import RetrievalHit, RetrievalResult


def _retrieval(*, with_hit: bool = True) -> RetrievalResult:
    if not with_hit:
        return RetrievalResult(
            query="Consulta fiscal sin evidencia",
            requested_top_k=5,
            candidate_count=0,
            returned_count=0,
            hits=[],
        )

    metadata = ChunkMetadata(
        document_id="doc-001",
        source_type=SourceType.NORMATIVA,
        source_filename="cuff.pdf",
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
        query="¿Existe una obligación fiscal aplicable?",
        requested_top_k=5,
        candidate_count=1,
        returned_count=1,
        hits=[
            RetrievalHit(
                rank=1,
                score=0.93,
                chunk_id="chunk-legal-001",
                text="Texto normativo autorizado para formular la hipótesis.",
                metadata=metadata,
            )
        ],
    )


def _valid_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "issue": "Posible obligación fiscal aplicable.",
        "hypothesis": (
            "Podría existir una obligación fiscal cuya procedencia debe "
            "verificarse mediante los motores jurídicos deterministas."
        ),
        "investigation_targets": [
            "Verificar sujeto, supuesto normativo, vigencia y temporalidad."
        ],
        "evidence_ids": ["chunk-legal-001"],
        "uncertainties": [],
        "status": "proposed",
        "requires_validation": True,
        "changes_deterministic_result": False,
        "asserts_external_legal_authority": False,
    }
    payload.update(overrides)
    return payload


class StaticProvider:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls = 0
        self.last_context: LLMGenerationContext | None = None
        self.last_schema: dict[str, object] | None = None

    @property
    def provider_name(self) -> str:
        return "static-llama"

    @property
    def model_name(self) -> str:
        return "llama-test"

    def generate_json(
        self,
        context: LLMGenerationContext,
        *,
        response_schema: dict[str, object],
    ) -> str:
        self.calls += 1
        self.last_context = context
        self.last_schema = response_schema
        return json.dumps(self.payload, ensure_ascii=False)


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


def test_service_generates_structured_controlled_hypothesis() -> None:
    provider = StaticProvider(_valid_payload())

    result = LlamaLegalHypothesisService(provider).generate(_retrieval())

    assert result.generation_performed is True
    assert result.hypothesis is not None
    assert result.hypothesis.status == LegalHypothesisStatus.PROPOSED
    assert result.hypothesis.requires_validation is True
    assert result.authorized_evidence_ids == ["chunk-legal-001"]
    assert "legal_hypothesis:provider=static-llama" in result.trace
    assert "legal_hypothesis:model=llama-test" in result.trace


def test_service_abstains_without_authorized_evidence() -> None:
    provider = StaticProvider(_valid_payload())

    result = LlamaLegalHypothesisService(provider).generate(
        _retrieval(with_hit=False)
    )

    assert result.generation_performed is False
    assert result.hypothesis is None
    assert result.requires_human_review is True
    assert provider.calls == 0


def test_service_builds_hypothesis_specific_controlled_context() -> None:
    provider = StaticProvider(_valid_payload())

    LlamaLegalHypothesisService(provider).generate(_retrieval())

    assert provider.last_context is not None
    assert provider.last_schema is not None
    assert [item.chunk_id for item in provider.last_context.evidence] == [
        "chunk-legal-001"
    ]
    instructions = " ".join(provider.last_context.presentation_instructions)
    assert "hipótesis jurídica inicial" in instructions
    assert "no emitas una conclusión jurídica definitiva" in instructions
    assert "requires_validation=true" in instructions
    assert "properties" in provider.last_schema


def test_service_rejects_invalid_structured_output() -> None:
    provider = StaticProvider({"issue": "Salida incompleta"})

    with pytest.raises(
        LLMResponseValidationError,
        match="contrato JSON esperado",
    ):
        LlamaLegalHypothesisService(provider).generate(_retrieval())


def test_service_rejects_unauthorized_evidence() -> None:
    provider = StaticProvider(
        _valid_payload(evidence_ids=["chunk-invented-999"])
    )

    with pytest.raises(
        LLMResponseValidationError,
        match="fuera del contexto autorizado",
    ):
        LlamaLegalHypothesisService(provider).generate(_retrieval())


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "changes_deterministic_result",
            True,
            "no puede modificar resultados jurídicos deterministas",
        ),
        (
            "asserts_external_legal_authority",
            True,
            "no puede introducir autoridad jurídica externa",
        ),
        (
            "requires_validation",
            False,
            "debe quedar sujeta a validación",
        ),
    ],
)
def test_service_rejects_hypothesis_that_crosses_legal_boundary(
    field: str,
    value: object,
    message: str,
) -> None:
    provider = StaticProvider(_valid_payload(**{field: value}))

    with pytest.raises(LLMResponseValidationError, match=message):
        LlamaLegalHypothesisService(provider).generate(_retrieval())


def test_service_wraps_unexpected_provider_failure() -> None:
    with pytest.raises(
        LLMGenerationError,
        match="falló al generar la hipótesis jurídica controlada",
    ):
        LlamaLegalHypothesisService(ExplodingProvider()).generate(_retrieval())
