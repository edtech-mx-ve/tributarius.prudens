from datetime import UTC, datetime

from app.domain.traceability import (
    CanonicalExecutionResult,
    EvidenceKind,
    EvidenceReference,
    TraceabilityRecord,
    TraceEvent,
    TraceEventStatus,
)
from app.web.presenter import present_canonical_result
from app.web.schemas import WebConsultationRequest


def _canonical() -> CanonicalExecutionResult:
    trace = TraceabilityRecord(
        execution_id="TP-" + ("A" * 32),
        folio="TP-20260829-" + ("B" * 12),
        created_at_utc=datetime(2026, 8, 29, tzinfo=UTC),
        query_sha256="a" * 64,
        primary_intent="tax_information",
        query_fiscal_year=2026,
        events=[
            TraceEvent(
                sequence=1,
                stage="retrieval",
                status=TraceEventStatus.COMPLETED,
                summary="Recuperación completada.",
                evidence_refs=["chunk-liva"],
            )
        ],
        evidence=[
            EvidenceReference(
                ref_id="chunk-liva",
                kind=EvidenceKind.DOCUMENT,
                source_type="normativa",
                source_reference="liva.md",
                version="2021-11-12",
                score=0.97,
            ),
            EvidenceReference(
                ref_id="chunk-unam",
                kind=EvidenceKind.DOCUMENT,
                source_type="unam",
                source_reference="manual_derecho_fiscal_unam.md",
                version="2020-01-01",
                score=0.88,
            ),
        ],
        requires_human_review=True,
        canonical_result_sha256="b" * 64,
    )
    return CanonicalExecutionResult(
        execution_id=trace.execution_id,
        folio=trace.folio,
        created_at_utc=trace.created_at_utc,
        query_analysis={},
        retrieval={
            "hits": [
                {
                    "chunk_id": "chunk-liva",
                    "text": "La Ley del IVA establece...",
                    "metadata": {
                        "document_id": "liva",
                        "title": "Ley del Impuesto al Valor Agregado",
                        "source_unit_label": "Artículo 1o",
                        "page_start": 1,
                        "page_end": 2,
                        "publication_date": "1978-12-29",
                        "effective_from": "2021-11-12",
                        "effective_to": None,
                    },
                },
                {
                    "chunk_id": "chunk-unam",
                    "text": "La tasa general se explica doctrinalmente...",
                    "metadata": {
                        "document_id": "manual_derecho_fiscal_unam",
                        "title": "Manual de Derecho Fiscal",
                        "source_unit_label": "Capítulo V",
                        "page_start": 129,
                        "page_end": 177,
                    },
                },
            ]
        },
        normative={"applicable_refs": []},
        rules={},
        calculations={"isr": None},
        cbr={},
        explanation=None,
        uncertainty={},
        traceability=trace,
    )


def test_presenter_separates_normative_and_supporting_evidence() -> None:
    result = present_canonical_result(
        _canonical(),
        WebConsultationRequest(
            query="¿Cuál es la tasa general de IVA?",
            mode="professional",
            fiscal_year=2026,
        ),
    )

    evidence = result["evidence"]
    assert isinstance(evidence, list)
    assert evidence[0]["role"] == "normative"
    assert evidence[0]["unit"] == "Artículo 1o"
    assert evidence[0]["snippet"] == "La Ley del IVA establece..."
    assert evidence[1]["role"] == "supporting"


def test_presenter_exposes_traceability_without_query_fingerprint() -> None:
    result = present_canonical_result(
        _canonical(),
        WebConsultationRequest(query="Consulta fiscal", fiscal_year=2026),
    )

    trace = result["traceability"]
    assert isinstance(trace, dict)
    assert trace["primary_intent"] == "tax_information"
    assert trace["query_fiscal_year"] == 2026
    assert trace["canonical_result_sha256"] == "b" * 64
    assert "query_sha256" not in trace
    assert trace["events"][0]["stage"] == "retrieval"
