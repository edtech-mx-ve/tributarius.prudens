from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.explanation_mode import ExplanationMode
from app.domain.legal_consultation_report import LegalConsultationReport
from app.services.legal_consultation_mode_explanation import (
    LegalConsultationModeExplanationError,
    build_legal_consultation_mode_explanation,
)
from app.services.legal_consultation_query_configuration import (
    build_legal_consultation_query_configuration,
)
from app.services.legal_explanation_profile import (
    get_legal_explanation_profile,
)
from app.services.traceability import build_canonical_result
from app.web.schemas import WebConsultationRequest
from tests.test_block12_4_hypothesis_verification import (
    _orchestrator,
    _request,
)
from tests.test_block_g1_legal_consultation_report import _NOW, _report


def _projection(mode: ExplanationMode = ExplanationMode.PROFESSIONAL):
    request = _request().model_copy(
        update={"explanation_mode": mode}
    )
    result = _orchestrator(None).run(request)
    canonical = build_canonical_result(
        request,
        result,
        now=_NOW,
    )

    web_request = WebConsultationRequest(
        query=request.query,
        mode=mode.value,
        fiscal_year=request.query_fiscal_year,
    )
    query_configuration = build_legal_consultation_query_configuration(
        web_request,
        request,
        canonical,
    )

    projection = build_legal_consultation_mode_explanation(
        canonical,
        query_configuration,
    )

    return request, result, canonical, query_configuration, projection


def test_g9_preserves_full_canonical_explanation_and_llm_trace() -> None:
    _, _, canonical, _, projection = _projection()

    assert projection.explanation_available is True
    assert projection.explanation is not None
    assert projection.llm_trace is not None

    assert (
        projection.explanation.model_dump(mode="json")
        == canonical.explanation
    )
    assert (
        projection.llm_trace.model_dump(mode="json")
        == canonical.llm_trace
    )

    assert projection.source_canonical_preserved is True
    assert projection.communication_profile_only is True
    assert projection.can_change_legal_decision is False
    assert projection.can_change_normative_basis is False
    assert projection.can_change_legal_authority is False
    assert projection.can_change_evidence is False
    assert projection.can_create_second_conclusion is False


def test_g9_supports_exactly_the_three_existing_modes() -> None:
    projected = {
        mode: _projection(mode)[4]
        for mode in ExplanationMode
    }

    assert set(projected) == {
        ExplanationMode.TAXPAYER,
        ExplanationMode.STUDENT,
        ExplanationMode.PROFESSIONAL,
    }

    for mode, projection in projected.items():
        assert projection.mode is mode
        assert projection.profile.mode is mode
        assert projection.llm_trace is not None
        assert projection.llm_trace.explanation_mode is mode

    assert len(
        {
            projection.profile.audience_label
            for projection in projected.values()
        }
    ) == 3


def test_g9_trace_matches_structured_explanation_exactly() -> None:
    _, _, _, _, projection = _projection()

    explanation = projection.explanation
    trace = projection.llm_trace

    assert explanation is not None
    assert trace is not None

    answer = explanation.answer

    assert trace.provider_name == explanation.provider_name
    assert trace.model_name == explanation.model_name
    assert trace.evidence_ids == answer.evidence_ids
    assert trace.normative_refs == answer.normative_refs
    assert trace.rule_refs == answer.rule_refs
    assert trace.calculation_refs == answer.calculation_refs
    assert trace.cbr_refs == answer.cbr_refs
    assert trace.jurisprudence_refs == answer.jurisprudence_refs
    assert trace.requires_human_review == answer.requires_human_review
    assert answer.changes_deterministic_result is False
    assert answer.asserts_external_legal_authority is False


def test_g9_rejects_mode_divergence_from_canonical_llm_trace() -> None:
    _, _, canonical, query_configuration, _ = _projection()

    altered_configuration = query_configuration.model_copy(
        update={"explanation_mode": ExplanationMode.TAXPAYER}
    )

    with pytest.raises(
        LegalConsultationModeExplanationError,
        match="modo distinto",
    ):
        build_legal_consultation_mode_explanation(
            canonical,
            altered_configuration,
        )


def test_g9_rejects_tampered_canonical_result() -> None:
    _, _, canonical, query_configuration, _ = _projection()

    tampered = canonical.model_copy(
        update={
            "explanation": {
                **canonical.explanation,
                "provider_name": "proveedor-alterado",
            }
        }
    )

    with pytest.raises(
        LegalConsultationModeExplanationError,
        match="resultado can",
    ):
        build_legal_consultation_mode_explanation(
            tampered,
            query_configuration,
        )


def test_g9_explicitly_preserves_absent_explanation_state() -> None:
    request = _request()
    result = _orchestrator(None).run(request)

    degraded = result.model_copy(
        update={
            "explanation": None,
            "llm_trace": None,
        }
    )
    canonical = build_canonical_result(
        request,
        degraded,
        now=_NOW,
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

    projection = build_legal_consultation_mode_explanation(
        canonical,
        query_configuration,
    )

    assert projection.explanation_available is False
    assert projection.generation_performed is False
    assert projection.explanation is None
    assert projection.llm_trace is None


def test_g9_report_requires_mode_explanation() -> None:
    report = _report()

    assert (
        report.mode_explanation.mode
        is report.query_configuration.explanation_mode
    )

    payload = report.model_dump(mode="python")
    payload.pop("mode_explanation")

    with pytest.raises(
        ValidationError,
        match="mode_explanation",
    ):
        LegalConsultationReport.model_validate(payload)


def test_g9_report_rejects_mode_divergence() -> None:
    report = _report()

    current = report.query_configuration.explanation_mode
    alternate = (
        ExplanationMode.TAXPAYER
        if current is not ExplanationMode.TAXPAYER
        else ExplanationMode.STUDENT
    )

    trace = report.mode_explanation.llm_trace
    altered_trace = (
        trace.model_copy(
            update={"explanation_mode": alternate}
        )
        if trace is not None
        else None
    )

    altered_projection = report.mode_explanation.model_copy(
        update={
            "mode": alternate,
            "profile": get_legal_explanation_profile(alternate),
            "llm_trace": altered_trace,
        }
    )

    payload = report.model_dump(mode="python")
    payload["mode_explanation"] = altered_projection

    with pytest.raises(
        ValidationError,
        match="mismo modo",
    ):
        LegalConsultationReport.model_validate(payload)


def test_g9_report_rejects_query_divergence() -> None:
    report = _report()
    explanation = report.mode_explanation.explanation

    assert explanation is not None

    altered_explanation = explanation.model_copy(
        update={"question": "Consulta diferente"}
    )
    altered_projection = report.mode_explanation.model_copy(
        update={"explanation": altered_explanation}
    )

    payload = report.model_dump(mode="python")
    payload["mode_explanation"] = altered_projection

    with pytest.raises(
        ValidationError,
        match="misma consulta",
    ):
        LegalConsultationReport.model_validate(payload)
