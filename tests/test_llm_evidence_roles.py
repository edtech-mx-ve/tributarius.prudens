from app.domain.chunks import ChunkMetadata, LegalChunkType, LegalHierarchy
from app.domain.documents import SourceType
from llm.models import DeterministicEvidence, LLMGenerationContext
from llm.service import LlamaRAGService
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


def _mixed_retrieval() -> RetrievalResult:
    return RetrievalResult(
        query="¿Cuáles son mis derechos fiscales?",
        requested_top_k=3,
        candidate_count=3,
        returned_count=3,
        hits=[
            _hit(1, SourceType.PRODECON, "prodecon-07"),
            _hit(2, SourceType.UNAM, "unam-capitulo-i"),
            _hit(3, SourceType.NORMATIVA, "lfdc-articulo-2"),
        ],
    )


def test_llm_context_receives_evidence_with_explicit_legal_functions() -> None:
    context = LlamaRAGService._context_from_retrieval(
        _mixed_retrieval(),
        deterministic_evidence=DeterministicEvidence(
            applicable_normative_refs=["lfdc-articulo-2"],
        ),
    )

    assert context.deterministic_evidence is not None
    assert context.deterministic_evidence.prodecon_orientation_refs == ["prodecon-07"]
    assert context.deterministic_evidence.unam_foundation_refs == ["unam-capitulo-i"]
    assert context.deterministic_evidence.normative_evidence_refs == ["lfdc-articulo-2"]
    assert context.deterministic_evidence.applicable_normative_refs == ["lfdc-articulo-2"]


def test_complementary_sources_cannot_become_applicable_norms_in_llm_context() -> None:
    context = LlamaRAGService._context_from_retrieval(
        _mixed_retrieval(),
        deterministic_evidence=DeterministicEvidence(),
    )

    assert context.deterministic_evidence is not None
    assert context.deterministic_evidence.applicable_normative_refs == []
    assert "prodecon-07" not in context.deterministic_evidence.normative_evidence_refs
    assert "unam-capitulo-i" not in context.deterministic_evidence.normative_evidence_refs


class CapturingProvider:
    def __init__(self) -> None:
        self.context: LLMGenerationContext | None = None

    @property
    def provider_name(self) -> str:
        return "capture"

    @property
    def model_name(self) -> str:
        return "capture-model"

    def generate_json(
        self,
        context: LLMGenerationContext,
        *,
        response_schema: dict[str, object],
    ) -> str:
        del response_schema
        self.context = context
        return (
            '{"summary":"s","analysis":"a","evidence_ids":["lfdc-articulo-2"],'
            '"uncertainties":[],"requires_human_review":false}'
        )


def test_explanation_provider_receives_separated_source_roles() -> None:
    provider = CapturingProvider()
    LlamaRAGService(provider).explain(
        _mixed_retrieval(),
        deterministic_evidence=DeterministicEvidence(
            applicable_normative_refs=["lfdc-articulo-2"],
        ),
    )

    assert provider.context is not None
    assert provider.context.deterministic_evidence is not None
    deterministic = provider.context.deterministic_evidence
    assert deterministic.prodecon_orientation_refs == ["prodecon-07"]
    assert deterministic.unam_foundation_refs == ["unam-capitulo-i"]
    assert deterministic.normative_evidence_refs == ["lfdc-articulo-2"]
