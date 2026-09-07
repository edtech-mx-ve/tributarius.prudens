from __future__ import annotations

import json

import pytest

from app.domain.jurisprudence_decision_application import (
    JurisprudenceDecisionEffect,
)
from app.domain.legal_consultation_report import LegalConsultationReport
from app.services.canonical_execution_snapshot import (
    build_canonical_execution_snapshot,
)
from app.services.integral_legal_analyzer import build_integral_legal_analysis
from app.services.jurisprudence_decision_application import (
    evaluate_jurisprudence_for_legal_decision,
)
from app.services.legal_consultation_applied_rbs import (
    build_legal_consultation_applied_rbs,
)
from app.services.legal_consultation_query_configuration import (
    build_legal_consultation_query_configuration,
)
from app.services.legal_consultation_session_jurisprudence import (
    LegalConsultationSessionJurisprudenceError,
    build_legal_consultation_session_jurisprudence,
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
from tests.test_block_e5_jurisprudence_evidence_integration import (
    DOC_ID,
    _document,
    _metadata,
    _ratio_record,
    _relation_record,
    _run,
    _temporal_record,
)
from tests.test_block_e6_analyzer_legal_decision import _analysis
from tests.test_block_g1_legal_consultation_report import _NOW


def _binding_execution():
    ratio = _ratio_record()
    relation = _relation_record()
    temporal = _temporal_record()

    session = _run(
        relation_record=relation,
        temporal_record=temporal,
    )

    application = evaluate_jurisprudence_for_legal_decision(
        analysis=_analysis(),
        session_result=session,
        ratio_records={DOC_ID: ratio},
        normative_relation_records={DOC_ID: relation},
    )

    session = session.model_copy(
        update={
            "decision_application": application,
            "requires_human_review": application.requires_human_review,
        }
    )

    request = _request().model_copy(
        update={
            "session_jurisprudence_documents": [_document()],
            "session_jurisprudence_metadata": {
                DOC_ID: _metadata(),
            },
            "session_jurisprudence_normative_relations": {
                DOC_ID: relation,
            },
            "session_jurisprudence_temporal_records": {
                DOC_ID: temporal,
            },
            "session_jurisprudence_ratio_records": {
                DOC_ID: ratio,
            },
        }
    )

    result = _orchestrator(None).run(request)
    result = result.model_copy(
        update={
            "session_jurisprudence_result": session,
            "requires_human_review": (
                result.requires_human_review
                or session.requires_human_review
            ),
        }
    )

    canonical = build_canonical_result(
        request,
        result,
        now=_NOW,
    )
    return request, result, canonical


def test_g7_no_attachment_is_explicit_and_has_no_effect() -> None:
    request = _request()
    result = _orchestrator(None).run(request)
    canonical = build_canonical_result(
        request,
        result,
        now=_NOW,
    )

    jurisprudence = build_legal_consultation_session_jurisprudence(
        request,
        result,
        canonical,
    )

    assert jurisprudence.user_attached is False
    assert jurisprudence.session_result is None
    assert jurisprudence.binding_jurisprudence_applies is False
    assert jurisprudence.governing_interpretation is False
    assert jurisprudence.external_search_performed is False


def test_g7_preserves_binding_session_jurisprudence_and_ratio() -> None:
    request, result, canonical = _binding_execution()

    jurisprudence = build_legal_consultation_session_jurisprudence(
        request,
        result,
        canonical,
    )

    assert jurisprudence.user_attached is True
    assert jurisprudence.binding_jurisprudence_applies is True
    assert jurisprudence.governing_interpretation is True
    assert jurisprudence.applicable_document_ids == [DOC_ID]
    assert jurisprudence.ratio_records[0].document_id == DOC_ID
    assert jurisprudence.ratio_records[0].ratio_source_established is True
    assert jurisprudence.ratio_records[0].ratio_source_text is not None

    application = jurisprudence.session_result.decision_application
    assert application is not None
    assessment = application.assessments[0]
    assert (
        assessment.decision_effect
        is JurisprudenceDecisionEffect.GOVERNING_INTERPRETATION
    )
    assert assessment.binding_jurisprudence_applies is True
    assert assessment.must_be_respected_by_legal_decision is True
    assert assessment.normative_basis_preserved is True
    assert assessment.can_replace_normative_basis is False
    assert assessment.can_create_second_conclusion is False


def test_g7_canonical_and_snapshot_preserve_ratio_source() -> None:
    _, _, canonical = _binding_execution()

    assert canonical.session_jurisprudence is not None
    assert canonical.session_jurisprudence_ratios is not None
    assert verify_canonical_integrity(canonical) is True

    snapshot = build_canonical_execution_snapshot(canonical)
    payload = json.loads(snapshot.canonical_json)

    assert (
        payload["session_jurisprudence"]
        == canonical.session_jurisprudence
    )
    assert (
        payload["session_jurisprudence_ratios"]
        == canonical.session_jurisprudence_ratios
    )


def test_g7_report_preserves_same_e6_application_and_single_conclusion() -> None:
    request, result, canonical = _binding_execution()

    jurisprudence = build_legal_consultation_session_jurisprudence(
        request,
        result,
        canonical,
    )

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
        jurisprudence_session_id="a" * 32,
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
        session_jurisprudence=jurisprudence,
        analyzer=analysis,
        legal_decision=decision,
        traceability=trace,
    )

    assert report.session_jurisprudence.governing_interpretation is True
    assert (
        report.analyzer.jurisprudence_application
        == report.legal_decision.jurisprudence_application
    )
    assert report.legal_decision.conclusion == report.analyzer.canonical_conclusion
    assert report.legal_decision.controlling_source != "jurisprudence"


def test_g7_non_equivalent_controversy_does_not_govern_interpretation() -> None:
    request, result, _ = _binding_execution()

    session = _run()
    application = evaluate_jurisprudence_for_legal_decision(
        analysis=_analysis(
            "Consulta completamente distinta sobre sanciones administrativas"
        ),
        session_result=session,
        ratio_records={DOC_ID: _ratio_record()},
        normative_relation_records={DOC_ID: _relation_record()},
    )
    session = session.model_copy(
        update={"decision_application": application}
    )
    result = result.model_copy(
        update={"session_jurisprudence_result": session}
    )
    canonical = build_canonical_result(
        request,
        result,
        now=_NOW,
    )

    jurisprudence = build_legal_consultation_session_jurisprudence(
        request,
        result,
        canonical,
    )

    assert jurisprudence.user_attached is True
    assert jurisprudence.binding_jurisprudence_applies is False
    assert jurisprudence.governing_interpretation is False


def test_g7_rejects_legacy_non_session_jurisprudence() -> None:
    request = _request()
    result = _orchestrator(None).run(request)
    canonical = build_canonical_result(
        request,
        result,
        now=_NOW,
    )

    tampered = canonical.model_copy(
        update={"jurisprudence": {"unauthorized": True}}
    )

    with pytest.raises(
        LegalConsultationSessionJurisprudenceError,
        match="ajena a la sesion",
    ):
        build_legal_consultation_session_jurisprudence(
            request,
            result,
            tampered,
        )
