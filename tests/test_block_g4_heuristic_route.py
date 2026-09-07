from __future__ import annotations

import json

import pytest

from app.domain.legal_consultation_report import LegalConsultationReport
from app.domain.legal_heuristics import LegalHeuristicEvaluation
from app.domain.orchestration import (
    HybridOrchestrationRequest,
    HybridOrchestrationResult,
    OrchestrationStage,
)
from app.domain.traceability import CanonicalExecutionResult
from app.services.canonical_execution_snapshot import (
    build_canonical_execution_snapshot,
)
from app.services.integral_legal_analyzer import build_integral_legal_analysis
from app.services.legal_consultation_heuristic_route import (
    LegalConsultationHeuristicRouteError,
    build_legal_consultation_heuristic_route,
)
from app.services.legal_consultation_query_configuration import (
    build_legal_consultation_query_configuration,
)
from app.services.legal_decision import build_legal_decision
from app.services.legal_heuristics_stage import run_legal_heuristics_stage
from app.services.traceability import (
    build_canonical_result,
    verify_canonical_integrity,
)
from app.web.schemas import WebConsultationRequest
from tests.test_block11_6_integral_acceptance import _coordination
from tests.test_block12_4_hypothesis_verification import _orchestrator, _request
from tests.test_block_g1_legal_consultation_report import _NOW


def _execution(
    *,
    with_heuristics: bool = True,
) -> tuple[
    HybridOrchestrationRequest,
    HybridOrchestrationResult,
    CanonicalExecutionResult,
]:
    request = _request()
    result = _orchestrator(None).run(request)

    if with_heuristics:
        coordination = _coordination()
        evaluation, heuristic_trace, heuristic_review = (
            run_legal_heuristics_stage(coordination)
        )
        assert evaluation is not None

        traces = [
            (
                heuristic_trace
                if item.stage == OrchestrationStage.LEGAL_HEURISTICS
                else item
            )
            for item in result.traces
        ]
        if not any(
            item.stage == OrchestrationStage.LEGAL_HEURISTICS
            for item in result.traces
        ):
            traces.append(heuristic_trace)

        result = result.model_copy(
            update={
                "hybrid_coordination": coordination,
                "heuristic_evaluation": evaluation,
                "traces": traces,
                "requires_human_review": (
                    result.requires_human_review or heuristic_review
                ),
            }
        )

    canonical = build_canonical_result(
        request,
        result,
        now=_NOW,
    )
    return request, result, canonical


def _report_from_execution(
    request: HybridOrchestrationRequest,
    result: HybridOrchestrationResult,
    canonical: CanonicalExecutionResult,
    route: LegalHeuristicEvaluation | None,
) -> LegalConsultationReport:
    analysis = build_integral_legal_analysis(result)
    decision = build_legal_decision(analysis)

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

    return LegalConsultationReport(
        execution_id=canonical.execution_id,
        folio=canonical.folio,
        created_at_utc=canonical.created_at_utc,
        canonical_result_sha256=trace.canonical_result_sha256,
        query_configuration=query_configuration,
        heuristic_route=route,
        analyzer=analysis,
        legal_decision=decision,
        traceability=trace,
    )


def test_g4_legitimately_skips_route_without_hybrid_coordination() -> None:
    _, result, canonical = _execution(with_heuristics=False)

    assert result.hybrid_coordination is None
    assert result.heuristic_evaluation is None
    assert canonical.legal_heuristics is None
    assert (
        build_legal_consultation_heuristic_route(result, canonical)
        is None
    )
    assert verify_canonical_integrity(canonical) is True


def test_g4_canonical_preserves_existing_heuristic_route() -> None:
    _, result, canonical = _execution()

    assert result.heuristic_evaluation is not None
    assert canonical.legal_heuristics == (
        result.heuristic_evaluation.model_dump(mode="json")
    )
    assert verify_canonical_integrity(canonical) is True


def test_g4_projects_route_without_recomputing_heuristics() -> None:
    _, result, canonical = _execution()

    route = build_legal_consultation_heuristic_route(
        result,
        canonical,
    )

    assert route is not None
    assert result.heuristic_evaluation is not None
    assert route == result.heuristic_evaluation
    assert route is not result.heuristic_evaluation
    assert (
        route.canonical_conclusion
        == result.heuristic_evaluation.canonical_conclusion
    )
    assert (
        route.controlling_source
        == result.heuristic_evaluation.controlling_source
    )
    assert route.controlling_source == "rbs"
    assert route.normative_priority_preserved is True


def test_g4_route_can_be_embedded_in_consistent_report() -> None:
    request, result, canonical = _execution()
    route = build_legal_consultation_heuristic_route(
        result,
        canonical,
    )

    report = _report_from_execution(
        request,
        result,
        canonical,
        route,
    )

    assert route is not None
    assert report.heuristic_route == route
    assert (
        report.analyzer.canonical_conclusion
        == route.canonical_conclusion
    )
    assert report.analyzer.controlling_source == route.controlling_source


def test_g4_snapshot_preserves_heuristic_route() -> None:
    _, _, canonical = _execution()

    snapshot = build_canonical_execution_snapshot(canonical)
    payload = json.loads(snapshot.canonical_json)

    assert canonical.legal_heuristics is not None
    assert payload["legal_heuristics"] == canonical.legal_heuristics


def test_g4_rejects_divergent_canonical_heuristic_route() -> None:
    _, result, canonical = _execution()

    assert canonical.legal_heuristics is not None
    altered = dict(canonical.legal_heuristics)
    altered["canonical_conclusion"] = "Resultado alterado."

    tampered = canonical.model_copy(
        update={"legal_heuristics": altered}
    )

    with pytest.raises(
        LegalConsultationHeuristicRouteError,
        match="divergencia",
    ):
        build_legal_consultation_heuristic_route(
            result,
            tampered,
        )
