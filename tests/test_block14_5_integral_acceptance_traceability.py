from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest

import app.web.runtime_runner as runtime_runner
from app.domain.explanation_mode import ExplanationMode
from app.services.integral_legal_analyzer import build_integral_legal_analysis
from app.services.integral_legal_traceability import (
    integral_legal_analysis_sha256,
    verify_integral_legal_analysis_integrity,
)
from app.services.traceability import build_canonical_result, verify_canonical_integrity
from app.web.presenter import present_integral_legal_analysis
from app.web.runtime_runner import WebHybridRunner
from app.web.schemas import WebConsultationRequest
from tests.test_block12_4_hypothesis_verification import _orchestrator, _request

_NOW = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)


def test_analyzer_1_0_integrity_hash_is_deterministic() -> None:
    result = _orchestrator(None).run(_request())
    analysis = build_integral_legal_analysis(result)

    first = integral_legal_analysis_sha256(analysis)
    second = integral_legal_analysis_sha256(analysis)

    assert first == second
    assert len(first) == 64
    assert verify_integral_legal_analysis_integrity(analysis, first) is True


def test_analyzer_integrity_detects_mutation() -> None:
    result = _orchestrator(None).run(_request())
    analysis = build_integral_legal_analysis(result)
    expected = integral_legal_analysis_sha256(analysis)

    analysis.applicable_normative_refs.append("REF-ALTERADA")

    assert verify_integral_legal_analysis_integrity(analysis, expected) is False


def test_analyzer_traceability_does_not_change_historical_canonical_hash() -> None:
    request = _request()
    result = _orchestrator(None).run(request)

    canonical_before = build_canonical_result(request, result, now=_NOW)
    analysis = build_integral_legal_analysis(result)
    integral_legal_analysis_sha256(analysis)
    canonical_after = build_canonical_result(request, result, now=_NOW)

    assert verify_canonical_integrity(canonical_before) is True
    assert verify_canonical_integrity(canonical_after) is True
    assert (
        canonical_before.traceability.canonical_result_sha256
        == canonical_after.traceability.canonical_result_sha256
    )


def test_presenter_exposes_integrity_hash_without_mode_or_explanation() -> None:
    result = _orchestrator(None).run(_request())
    analysis = build_integral_legal_analysis(result)

    presented = present_integral_legal_analysis(analysis)

    assert presented["integrity_sha256"] == integral_legal_analysis_sha256(analysis)
    assert "mode" not in presented
    assert "explanation" not in presented
    assert "explanation_profile" not in presented


def test_analyzer_1_0_is_invariant_across_all_explanation_modes() -> None:
    analyses = []
    for mode in (
        ExplanationMode.TAXPAYER,
        ExplanationMode.STUDENT,
        ExplanationMode.PROFESSIONAL,
    ):
        request = _request().model_copy(update={"explanation_mode": mode})
        result = _orchestrator(None).run(request)
        analysis = build_integral_legal_analysis(result)
        analyses.append(analysis)

    assert analyses[0] == analyses[1] == analyses[2]
    assert (
        integral_legal_analysis_sha256(analyses[0])
        == integral_legal_analysis_sha256(analyses[1])
        == integral_legal_analysis_sha256(analyses[2])
    )


def test_analyzer_never_promotes_llm_to_controlling_source() -> None:
    result = _orchestrator("Hipótesis provisional generada por Llama.").run(_request())
    analysis = build_integral_legal_analysis(result)

    assert analysis.controlling_source in {None, "rbs"}
    assert analysis.controlling_source != "llm"
    assert analysis.controlling_source != "explanation"
    assert analysis.controlling_source != "legal_hypothesis"


def test_analyzer_acceptance_preserves_one_canonical_legal_conclusion() -> None:
    result = _orchestrator(None).run(_request())
    analysis = build_integral_legal_analysis(result)

    if result.heuristic_evaluation is not None:
        expected = result.heuristic_evaluation.canonical_conclusion
    elif result.hybrid_coordination is not None:
        expected = result.hybrid_coordination.conclusion
    else:
        expected = result.rule_result.matched_rules[0].conclusion

    assert analysis.canonical_conclusion == expected
    assert analysis.readiness.can_close_automatically is True


def test_web_runtime_exposes_verified_analyzer_integrity(
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

    presented = cast(dict[str, object], response["legal_analysis"])
    analysis = build_integral_legal_analysis(result)

    assert presented["integrity_sha256"] == integral_legal_analysis_sha256(analysis)
    assert presented["canonical_conclusion"] == analysis.canonical_conclusion
    assert presented["controlling_source"] == analysis.controlling_source
