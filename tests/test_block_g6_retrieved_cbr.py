from __future__ import annotations

import json

import pytest

from app.domain.hybrid_reasoning import ReasoningSource
from app.domain.legal_consultation_report import LegalConsultationReport
from app.services.canonical_execution_snapshot import (
    build_canonical_execution_snapshot,
)
from app.services.integral_legal_analyzer import build_integral_legal_analysis
from app.services.legal_consultation_applied_rbs import (
    build_legal_consultation_applied_rbs,
)
from app.services.legal_consultation_query_configuration import (
    build_legal_consultation_query_configuration,
)
from app.services.legal_consultation_retrieved_cbr import (
    LegalConsultationRetrievedCBRError,
    build_legal_consultation_retrieved_cbr,
)
from app.services.legal_decision import build_legal_decision
from app.services.traceability import (
    build_canonical_result,
    verify_canonical_integrity,
)
from app.web.schemas import WebConsultationRequest
from tests.test_block12_4_hypothesis_verification import (
    _orchestrator,
    _request,
)
from tests.test_block_g1_legal_consultation_report import _NOW
from tests.test_cbr_hybrid_integration import (
    cbr_case,
)
from tests.test_cbr_hybrid_integration import (
    request as cbr_request,
)
from tests.test_cbr_hybrid_integration import (
    service as cbr_service,
)


def _cbr_execution():
    request = cbr_request()
    result = cbr_service([cbr_case()]).run(request)
    canonical = build_canonical_result(
        request,
        result,
        now=_NOW,
    )
    return request, result, canonical


def test_g6_canonical_preserves_retrieval_reuse_and_reasoning() -> None:
    _, result, canonical = _cbr_execution()

    assert result.cbr_result is not None
    assert result.cbr_reasoning is not None

    assert canonical.cbr["retrieval"] == (
        result.cbr_result.model_dump(mode="json")
    )
    assert canonical.cbr["reuse_assessments"] == [
        item.model_dump(mode="json")
        for item in result.cbr_reuse_assessments
    ]
    assert canonical.cbr_reasoning == (
        result.cbr_reasoning.model_dump(mode="json")
    )
    assert verify_canonical_integrity(canonical) is True


def test_g6_preserves_eligible_case_as_analogical_support_only() -> None:
    _, result, canonical = _cbr_execution()

    retrieved = build_legal_consultation_retrieved_cbr(
        result,
        canonical,
    )

    assert retrieved is not None
    assert retrieved.retrieval is not None
    assert retrieved.retrieval.returned_count == 1
    assert retrieved.retrieval.matches[0].case_id == "CASE-CBR-001"

    assert len(retrieved.reuse_assessments) == 1
    assert retrieved.reuse_assessments[0].decision.value == "eligible"

    assert (
        retrieved.normalized_reasoning.reasoning_source
        is ReasoningSource.CBR
    )
    assert retrieved.hybrid_controlling_source == "rbs"
    assert retrieved.analogical_role_preserved is True
    assert retrieved.can_be_legal_authority is False
    assert retrieved.can_control_legal_decision is False


def test_g6_can_be_embedded_in_consistent_report() -> None:
    request, result, canonical = _cbr_execution()

    retrieved = build_legal_consultation_retrieved_cbr(
        result,
        canonical,
    )
    assert retrieved is not None

    analysis = build_integral_legal_analysis(result)
    decision = build_legal_decision(analysis)
    applied_rbs = build_legal_consultation_applied_rbs(
        result,
        canonical,
    )

    web_request = WebConsultationRequest(
        query=request.query,
        mode=request.explanation_mode.value,
        fiscal_year=request.query_fiscal_year,
    )
    query_configuration = build_legal_consultation_query_configuration(
        web_request,
        request,
        canonical,
    )

    trace = canonical.traceability
    assert trace.canonical_result_sha256 is not None

    report = LegalConsultationReport(
        execution_id=canonical.execution_id,
        folio=canonical.folio,
        created_at_utc=canonical.created_at_utc,
        canonical_result_sha256=trace.canonical_result_sha256,
        query_configuration=query_configuration,
        applied_rbs=applied_rbs,
        retrieved_cbr=retrieved,
        analyzer=analysis,
        legal_decision=decision,
        traceability=trace,
    )

    assert report.retrieved_cbr is not None
    assert report.retrieved_cbr.hybrid_controlling_source == "rbs"
    assert report.applied_rbs.determinative_role_preserved is True
    assert report.retrieved_cbr.can_control_legal_decision is False


def test_g6_snapshot_preserves_full_cbr_state() -> None:
    _, _, canonical = _cbr_execution()

    snapshot = build_canonical_execution_snapshot(canonical)
    payload = json.loads(snapshot.canonical_json)

    assert payload["cbr"] == canonical.cbr
    assert payload["cbr_reasoning"] == canonical.cbr_reasoning


def test_g6_returns_none_when_cbr_was_not_requested() -> None:
    request = _request()
    result = _orchestrator(None).run(request)
    canonical = build_canonical_result(
        request,
        result,
        now=_NOW,
    )

    assert result.cbr_result is None
    assert result.cbr_reasoning is None
    assert (
        build_legal_consultation_retrieved_cbr(
            result,
            canonical,
        )
        is None
    )


def test_g6_preserves_degraded_requested_cbr_without_corpus() -> None:
    request = cbr_request()
    result = cbr_service([]).run(request)
    canonical = build_canonical_result(
        request,
        result,
        now=_NOW,
    )

    retrieved = build_legal_consultation_retrieved_cbr(
        result,
        canonical,
    )

    assert retrieved is not None
    assert retrieved.retrieval is None
    assert retrieved.reuse_assessments == []
    assert retrieved.normalized_reasoning.requires_review is True
    assert retrieved.normalized_reasoning.trace == ["cbr:no_result"]
    assert retrieved.can_control_legal_decision is False


def test_g6_rejects_divergent_canonical_cbr_reasoning() -> None:
    _, result, canonical = _cbr_execution()

    tampered = canonical.model_copy(
        update={
            "cbr_reasoning": {
                "reasoning_source": "cbr",
                "conclusion": "Resultado analogico alterado.",
            }
        }
    )

    with pytest.raises(
        LegalConsultationRetrievedCBRError,
        match="divergencia",
    ):
        build_legal_consultation_retrieved_cbr(
            result,
            tampered,
        )
