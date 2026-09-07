from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.domain.legal_consultation_report import LegalConsultationReport
from app.services.hybrid_legal_decision import build_hybrid_legal_decision
from app.services.integral_legal_analyzer import build_integral_legal_analysis
from app.services.legal_decision import build_legal_decision
from app.services.traceability import build_canonical_result
from tests.test_block12_4_hypothesis_verification import _orchestrator, _request
from tests.test_block_f9_hybrid_legal_decision import _verified_analysis

_NOW = datetime(2026, 9, 7, 2, 30, tzinfo=UTC)


def _components():
    request = _request()
    result = _orchestrator(None).run(request)
    canonical = build_canonical_result(request, result, now=_NOW)
    analysis = build_integral_legal_analysis(result)
    decision = build_legal_decision(analysis)
    return canonical, analysis, decision


def _report(
    *,
    analyzer=None,
    legal_decision=None,
) -> LegalConsultationReport:
    canonical, base_analysis, base_decision = _components()
    trace = canonical.traceability

    assert trace.canonical_result_sha256 is not None

    return LegalConsultationReport(
        execution_id=canonical.execution_id,
        folio=canonical.folio,
        created_at_utc=canonical.created_at_utc,
        canonical_result_sha256=trace.canonical_result_sha256,
        analyzer=analyzer if analyzer is not None else base_analysis,
        legal_decision=(
            legal_decision if legal_decision is not None else base_decision
        ),
        traceability=trace,
    )


def test_g1_aggregates_existing_legal_results_without_recomputing_them() -> None:
    report = _report()

    assert report.schema_version == "1.0"
    assert report.execution_id == report.traceability.execution_id
    assert report.folio == report.traceability.folio
    assert (
        report.canonical_result_sha256
        == report.traceability.canonical_result_sha256
    )
    assert report.legal_decision.conclusion == report.analyzer.canonical_conclusion
    assert (
        report.legal_decision.applicable_normative_refs
        == report.analyzer.applicable_normative_refs
    )


def test_g1_rejects_a_second_legal_conclusion() -> None:
    canonical, analysis, decision = _components()
    trace = canonical.traceability
    assert trace.canonical_result_sha256 is not None

    altered_decision = decision.model_copy(
        update={"conclusion": "Conclusion juridica diferente."}
    )

    with pytest.raises(ValidationError, match="segunda conclusi"):
        LegalConsultationReport(
            execution_id=canonical.execution_id,
            folio=canonical.folio,
            created_at_utc=canonical.created_at_utc,
            canonical_result_sha256=trace.canonical_result_sha256,
            analyzer=analysis,
            legal_decision=altered_decision,
            traceability=trace,
        )


def test_g1_preserves_hybrid_f8_f9_contracts_without_truncation() -> None:
    analysis = _verified_analysis()
    decision = build_hybrid_legal_decision(analysis)

    report = _report(
        analyzer=analysis,
        legal_decision=decision,
    )
    payload = report.model_dump(mode="json")

    assert (
        payload["analyzer"]["hybrid_projection"]["reasoning_controller"]
        == "rbs"
    )
    assert (
        payload["legal_decision"]["hybrid_projection"]["legal_authority_source"]
        == "normative_evidence"
    )
    assert (
        payload["legal_decision"]["hybrid_projection"][
            "single_determination_preserved"
        ]
        is True
    )
