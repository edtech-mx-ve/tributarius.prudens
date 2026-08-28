import json
from datetime import UTC, date, datetime

from app.domain.orchestration import HybridOrchestrationRequest
from app.services.hybrid_orchestrator import HybridOrchestrator
from app.services.traceability import (
    build_canonical_result,
    verify_canonical_integrity,
    verify_query_fingerprint,
)
from app.services.traced_orchestrator import TracedHybridOrchestrator
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


def build_result():
    request = HybridOrchestrationRequest(
        query="Calcula ISR sin registrar texto sensible",
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
    return request, service.run(request)


def test_canonical_result_has_folio_and_integrity_hash() -> None:
    request, result = build_result()
    canonical = build_canonical_result(
        request,
        result,
        now=datetime(2026, 8, 28, 12, 0, tzinfo=UTC),
    )

    assert canonical.folio.startswith("TP-20260828-")
    assert canonical.execution_id.startswith("TP-")
    assert canonical.traceability.canonical_result_sha256 is not None
    assert verify_canonical_integrity(canonical) is True
    assert verify_query_fingerprint(request.query, canonical.traceability) is True


def test_trace_record_does_not_store_raw_query() -> None:
    request, result = build_result()
    canonical = build_canonical_result(request, result)
    trace_json = json.dumps(canonical.traceability.model_dump(mode="json"))
    assert request.query not in trace_json
    assert canonical.traceability.query_sha256


def test_events_are_sequential_and_reference_evidence() -> None:
    request, result = build_result()
    canonical = build_canonical_result(request, result)
    events = canonical.traceability.events

    assert [item.sequence for item in events] == list(range(1, len(events) + 1))
    retrieval_event = next(item for item in events if item.stage == "retrieval")
    normative_event = next(item for item in events if item.stage == "normative")
    rule_event = next(item for item in events if item.stage == "rules")
    isr_event = next(item for item in events if item.stage == "isr")

    assert retrieval_event.evidence_refs == ["normativa-test-chunk-00001"]
    assert normative_event.evidence_refs == ["NORM_TEST_ISR_2026"]
    assert rule_event.evidence_refs == ["ISR_RULE_001@1.0"]
    assert isr_event.evidence_refs == ["ISR@TEST-1.0"]


def test_tampering_breaks_integrity_verification() -> None:
    request, result = build_result()
    canonical = build_canonical_result(request, result)
    canonical.calculations["isr"]["final_tax"] = "999999.99"
    assert verify_canonical_integrity(canonical) is False


def test_traced_orchestrator_returns_canonical_boundary() -> None:
    request = HybridOrchestrationRequest(
        query="Calcula ISR",
        query_date=date(2026, 8, 28),
        query_fiscal_year=2026,
        normative_candidates=[candidate()],
        isr_input=isr_input(),
    )
    hybrid = HybridOrchestrator(
        query_analyzer=FakeAnalyzer(analysis()),
        retriever=FakeRetriever(retrieval()),
        llm_service=LlamaRAGService(MockLLMProvider()),
        rule_set=rules(),
        isr_tariff=tariff(),
    )
    canonical = TracedHybridOrchestrator(hybrid).run(
        request,
        now=datetime(2026, 8, 28, 12, 0, tzinfo=UTC),
    )
    assert canonical.traceability.folio == canonical.folio
    assert verify_canonical_integrity(canonical) is True
