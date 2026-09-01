import json
from datetime import date
from pathlib import Path

import pytest

from app.domain.orchestration import HybridOrchestrationRequest
from app.domain.traceability import CanonicalExecutionResult
from app.services.hybrid_orchestrator import HybridOrchestrator
from app.services.trace_exporter import TraceExportError, export_canonical_json
from app.services.traceability import build_canonical_result
from llm.providers.mock import MockLLMProvider
from llm.service import LlamaRAGService
from tests.test_hybrid_orchestrator import (
    FakeAnalyzer,
    FakeRetriever,
    analysis,
    candidate,
    isr_input,
    retrieval,
    rules,
    tariff,
)


def canonical_result() -> CanonicalExecutionResult:
    request = HybridOrchestrationRequest(
        query="Calcula ISR",
        query_date=date(2026, 8, 28),
        query_fiscal_year=2026,
        normative_candidates=[candidate()],
        isr_input=isr_input(),
    )
    service = HybridOrchestrator(
        query_analyzer=FakeAnalyzer(analysis()),
        retriever=FakeRetriever(retrieval()),
        llm_service=LlamaRAGService(MockLLMProvider()),
        rule_set=rules(),
        isr_tariff=tariff(),
    )
    return build_canonical_result(request, service.run(request))


def test_export_canonical_json(tmp_path: Path) -> None:
    output = tmp_path / "trace.json"
    export_canonical_json(canonical_result(), output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["folio"].startswith("TP-")


def test_export_does_not_overwrite_by_default(tmp_path: Path) -> None:
    output = tmp_path / "trace.json"
    export_canonical_json(canonical_result(), output)
    with pytest.raises(TraceExportError):
        export_canonical_json(canonical_result(), output)


def test_export_requires_json_extension(tmp_path: Path) -> None:
    with pytest.raises(TraceExportError):
        export_canonical_json(canonical_result(), tmp_path / "trace.txt")
