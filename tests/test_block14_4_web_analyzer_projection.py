from __future__ import annotations

from typing import cast

import pytest

import app.web.runtime_runner as runtime_runner
from app.domain.integral_legal_analysis import IntegralLegalAnalysisStatus
from app.services.integral_legal_analyzer import build_integral_legal_analysis
from app.web.presenter import present_integral_legal_analysis
from app.web.runtime_runner import WebHybridRunner
from app.web.schemas import WebConsultationRequest
from tests.test_block12_4_hypothesis_verification import _orchestrator, _request


def test_presenter_exposes_analyzer_1_0_without_reinterpreting_result() -> None:
    result = _orchestrator(None).run(_request())
    analysis = build_integral_legal_analysis(result)

    presented = present_integral_legal_analysis(analysis)

    assert presented["schema_version"] == "1.0"
    assert presented["status"] == IntegralLegalAnalysisStatus.READY.value
    assert presented["canonical_conclusion"] == analysis.canonical_conclusion
    assert presented["controlling_source"] == analysis.controlling_source
    assert presented["requires_human_review"] == analysis.requires_human_review


def test_presenter_exposes_readiness_and_exact_five_evidence_channels() -> None:
    result = _orchestrator(None).run(_request())
    analysis = build_integral_legal_analysis(result)

    presented = present_integral_legal_analysis(analysis)
    readiness = cast(dict[str, object], presented["readiness"])
    evidence_map = cast(dict[str, object], presented["evidence_map"])
    items = cast(list[dict[str, object]], evidence_map["items"])

    assert readiness["can_close_automatically"] is True
    assert readiness["evidentiary_sufficiency"] == "sufficient"
    assert [item["channel"] for item in items] == [
        "normative",
        "rbs",
        "cbr",
        "jurisprudence",
        "calculation",
    ]


def test_presenter_keeps_missing_optional_channels_explicit() -> None:
    result = _orchestrator(None).run(_request())
    presented = present_integral_legal_analysis(
        build_integral_legal_analysis(result)
    )
    evidence_map = cast(dict[str, object], presented["evidence_map"])
    items = cast(list[dict[str, object]], evidence_map["items"])

    by_channel = {cast(str, item["channel"]): item for item in items}
    assert by_channel["cbr"]["present"] is False
    assert by_channel["jurisprudence"]["present"] is False
    assert by_channel["cbr"]["references"] == []
    assert by_channel["jurisprudence"]["references"] == []


def test_web_runner_includes_integral_legal_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestrator = _orchestrator(None)
    result = orchestrator.run(_request())

    monkeypatch.setattr(
        runtime_runner,
        "run_hybrid_with_session_jurisprudence",
        lambda _orchestrator_arg, _request_arg: result,
    )

    runner = WebHybridRunner(
        orchestrator=orchestrator,
        retrieval_runtime="test",
        explanation_runtime="test",
    )
    response = runner.run(
        WebConsultationRequest(
            query="Calcula ISR",
            mode="professional",
            fiscal_year=2026,
        )
    )

    assert "legal_analysis" in response
    legal_analysis = cast(dict[str, object], response["legal_analysis"])
    assert legal_analysis["schema_version"] == "1.0"
    assert legal_analysis["status"] == "ready"
    assert legal_analysis["canonical_conclusion"] == (
        result.rule_result.matched_rules[0].conclusion
    )
    assert legal_analysis["controlling_source"] == "rbs"


def test_web_analyzer_projection_is_mode_invariant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestrator = _orchestrator(None)
    result = orchestrator.run(_request())

    monkeypatch.setattr(
        runtime_runner,
        "run_hybrid_with_session_jurisprudence",
        lambda _orchestrator_arg, _request_arg: result,
    )
    runner = WebHybridRunner(
        orchestrator=orchestrator,
        retrieval_runtime="test",
        explanation_runtime="test",
    )

    projections: list[dict[str, object]] = []
    for mode in ("taxpayer", "student", "professional"):
        response = runner.run(
            WebConsultationRequest(
                query="Calcula ISR",
                mode=mode,
                fiscal_year=2026,
            )
        )
        projections.append(cast(dict[str, object], response["legal_analysis"]))

    assert projections[0] == projections[1] == projections[2]


def test_analyzer_projection_does_not_replace_existing_canonical_fields() -> None:
    result = _orchestrator(None).run(_request())
    analysis = build_integral_legal_analysis(result)

    presented = present_integral_legal_analysis(analysis)

    assert "explanation" not in presented
    assert "mode" not in presented
    assert "explanation_profile" not in presented
