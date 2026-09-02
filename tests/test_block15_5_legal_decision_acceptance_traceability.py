from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

import app.web.runtime_runner as runtime_runner
from app.domain.explanation_mode import ExplanationMode
from app.domain.legal_decision import LegalDecision
from app.services.integral_legal_analyzer import build_integral_legal_analysis
from app.services.legal_decision import build_legal_decision
from app.services.legal_decision_traceability import (
    legal_decision_sha256,
    verify_legal_decision_integrity,
)
from app.services.traceability import build_canonical_result, verify_canonical_integrity
from app.web.presenter import present_legal_decision
from app.web.runtime_runner import WebHybridRunner
from app.web.schemas import WebConsultationRequest
from tests.test_block12_4_hypothesis_verification import _orchestrator, _request

_NOW = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)


def _decision() -> LegalDecision:
    result = _orchestrator(None).run(_request())
    analysis = build_integral_legal_analysis(result)
    return build_legal_decision(analysis)


def test_legal_decision_integrity_hash_is_deterministic() -> None:
    decision = _decision()
    first = legal_decision_sha256(decision)
    second = legal_decision_sha256(decision)
    assert first == second
    assert len(first) == 64
    assert verify_legal_decision_integrity(decision, first) is True


def test_legal_decision_integrity_detects_mutation() -> None:
    decision = _decision()
    expected = legal_decision_sha256(decision)
    decision.applicable_normative_refs.append("REF-ALTERADA")
    assert verify_legal_decision_integrity(decision, expected) is False


def test_legal_decision_traceability_preserves_historical_canonical_hash() -> None:
    request = _request()
    result = _orchestrator(None).run(request)
    canonical_before = build_canonical_result(request, result, now=_NOW)
    analysis = build_integral_legal_analysis(result)
    decision = build_legal_decision(analysis)
    legal_decision_sha256(decision)
    canonical_after = build_canonical_result(request, result, now=_NOW)

    assert verify_canonical_integrity(canonical_before) is True
    assert verify_canonical_integrity(canonical_after) is True
    assert (
        canonical_before.traceability.canonical_result_sha256
        == canonical_after.traceability.canonical_result_sha256
    )


def test_presenter_exposes_legal_decision_with_own_integrity_hash() -> None:
    decision = _decision()
    presented = present_legal_decision(decision)

    assert presented["integrity_sha256"] == legal_decision_sha256(decision)
    assert presented["conclusion"] == decision.conclusion
    assert presented["controlling_source"] == decision.controlling_source
    assert presented["reasoning_chain"] == decision.reasoning_chain.model_dump(mode="json")
    assert presented["consequences"] == decision.consequences.model_dump(mode="json")


def test_legal_decision_is_invariant_across_explanation_modes() -> None:
    decisions = []
    for mode in (
        ExplanationMode.TAXPAYER,
        ExplanationMode.STUDENT,
        ExplanationMode.PROFESSIONAL,
    ):
        request = _request().model_copy(update={"explanation_mode": mode})
        result = _orchestrator(None).run(request)
        analysis = build_integral_legal_analysis(result)
        decisions.append(build_legal_decision(analysis))

    assert decisions[0] == decisions[1] == decisions[2]
    assert (
        legal_decision_sha256(decisions[0])
        == legal_decision_sha256(decisions[1])
        == legal_decision_sha256(decisions[2])
    )


def test_legal_decision_preserves_analyzer_conclusion_and_controller() -> None:
    result = _orchestrator(None).run(_request())
    analysis = build_integral_legal_analysis(result)
    decision = build_legal_decision(analysis)

    assert decision.conclusion == analysis.canonical_conclusion
    assert decision.controlling_source == analysis.controlling_source
    assert decision.controlling_source != "llama"


def test_legal_decision_never_downgrades_human_review() -> None:
    result = _orchestrator(None).run(_request())
    analysis = build_integral_legal_analysis(result)
    analysis.requires_human_review = True
    decision = build_legal_decision(analysis)
    assert decision.requires_human_review is True


def test_web_runtime_exposes_verified_legal_decision(
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

    presented = cast(dict[str, object], response["legal_decision"])
    analysis = build_integral_legal_analysis(result)
    decision = build_legal_decision(analysis)

    assert presented["integrity_sha256"] == legal_decision_sha256(decision)
    assert presented["conclusion"] == analysis.canonical_conclusion
    assert presented["controlling_source"] == analysis.controlling_source


def test_web_template_contains_legal_decision_1_0_surface() -> None:
    template = Path("app/web/templates/index.html").read_text(encoding="utf-8")
    javascript = Path("app/web/static/js/app.js").read_text(encoding="utf-8")

    assert 'id="legal-decision-block"' in template
    assert 'id="legal-decision-integrity-hash"' in template
    assert "function renderLegalDecision(result)" in javascript
    assert "renderLegalDecision(result);" in javascript
