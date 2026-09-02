from datetime import date
from typing import Any, cast

from app.domain.jurisprudence_document import (
    JurisprudenceDocumentRepresentation,
    JurisprudencePage,
)
from app.domain.jurisprudence_extraction import JurisprudenceExtractedMetadata
from app.domain.orchestration import (
    HybridOrchestrationRequest,
    HybridOrchestrationResult,
    OrchestrationStage,
    StageStatus,
)
from app.domain.query import QueryAnalysis, QueryIntent
from app.services.hybrid_jurisprudence_integration import (
    run_hybrid_with_session_jurisprudence,
)

SHA = "d" * 64


class FakeOrchestrator:
    def __init__(self, result: HybridOrchestrationResult) -> None:
        self.result = result

    def run(self, request: HybridOrchestrationRequest) -> HybridOrchestrationResult:
        del request
        return self.result


def _document() -> JurisprudenceDocumentRepresentation:
    text = "Devolución conforme al artículo 22 del CFF."
    return JurisprudenceDocumentRepresentation(
        document_id="jurisprudencia-session",
        original_filename="criterio.pdf",
        source_sha256=SHA,
        page_count=1,
        extracted_characters=len(text),
        pages=[JurisprudencePage(number=1, text=text, has_extractable_text=True)],
        full_text=text,
    )


def _metadata() -> JurisprudenceExtractedMetadata:
    return JurisprudenceExtractedMetadata(
        identifier="20260009",
        title="DEVOLUCIÓN.",
        court_or_body="Primera Sala",
        matter=None,
        related_normative_refs=[],
        source_pages=[1],
        requires_human_review=True,
    )


def _base_result() -> HybridOrchestrationResult:
    analysis = QueryAnalysis.model_construct(
        original_query="¿Procede la devolución?",
        normalized_query="devolución artículo 22",
        primary_intent=QueryIntent.RELATED_JURISPRUDENCE,
        facts=[],
    )
    return HybridOrchestrationResult.model_construct(
        analysis=analysis,
        retrieval=cast(Any, None),
        normative_results=[],
        applicable_normative_refs=["Artículo 22 de CFF"],
        rule_result=cast(Any, None),
        traces=[],
        requires_human_review=False,
        session_jurisprudence_result=None,
    )


def test_request_accepts_temporary_jurisprudence_without_affecting_defaults() -> None:
    request = HybridOrchestrationRequest(
        query="¿Procede la devolución?",
        query_date=date(2026, 9, 2),
    )

    assert request.session_jurisprudence_documents == []
    assert request.session_jurisprudence_metadata == {}


def test_integration_adds_session_result_without_overwriting_base_layers() -> None:
    base = _base_result()
    request = HybridOrchestrationRequest(
        query="¿Procede la devolución?",
        query_date=date(2026, 9, 2),
        session_jurisprudence_documents=[_document()],
        session_jurisprudence_metadata={"jurisprudencia-session": _metadata()},
    )

    result = run_hybrid_with_session_jurisprudence(FakeOrchestrator(base), request)

    assert result.session_jurisprudence_result is not None
    assert result.applicable_normative_refs == ["Artículo 22 de CFF"]
    assert result.rule_result is base.rule_result
    assert result.requires_human_review is True
    assert result.traces[-1].stage is OrchestrationStage.JURISPRUDENCE
    assert result.traces[-1].status is StageStatus.COMPLETED


def test_without_session_documents_returns_original_result() -> None:
    base = _base_result()
    request = HybridOrchestrationRequest(
        query="¿Procede la devolución?",
        query_date=date(2026, 9, 2),
    )

    result = run_hybrid_with_session_jurisprudence(FakeOrchestrator(base), request)

    assert result is base
    assert result.session_jurisprudence_result is None
