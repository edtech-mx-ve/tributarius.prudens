from __future__ import annotations

from pathlib import Path

import pytest

from app.services.integral_legal_analyzer import (
    build_integral_legal_analysis,
)
from app.services.legal_consultation_pdf_artifact import (
    build_legal_consultation_pdf_artifact,
)
from app.services.legal_consultation_report import (
    build_legal_consultation_report,
)
from app.services.legal_decision import build_legal_decision
from app.services.traceability import build_canonical_result
from app.web.legal_consultation_pdf_store import (
    WebLegalConsultationPdfStoreError,
    load_web_legal_consultation_pdf_artifact,
    save_web_legal_consultation_pdf_artifact,
)
from app.web.schemas import WebConsultationRequest
from tests.test_block12_4_hypothesis_verification import (
    _orchestrator,
    _request,
)
from tests.test_block_g1_legal_consultation_report import (
    _NOW,
)


def _production_report():
    orchestration_request = _request()
    result = _orchestrator(None).run(
        orchestration_request
    )

    canonical = build_canonical_result(
        orchestration_request,
        result,
        now=_NOW,
    )

    analyzer = build_integral_legal_analysis(
        result
    )
    decision = build_legal_decision(
        analyzer
    )

    web_request = WebConsultationRequest(
        query=orchestration_request.query,
        mode=(
            orchestration_request
            .explanation_mode.value
        ),
        fiscal_year=(
            orchestration_request
            .query_fiscal_year
        ),
    )

    report = build_legal_consultation_report(
        web_request=web_request,
        orchestration_request=orchestration_request,
        result=result,
        canonical=canonical,
        analyzer=analyzer,
        legal_decision=decision,
    )

    return (
        orchestration_request,
        result,
        canonical,
        report,
    )


def test_g12_builds_report_from_same_execution() -> None:
    _, _, canonical, report = _production_report()

    assert report.execution_id == canonical.execution_id
    assert report.folio == canonical.folio

    assert (
        report.canonical_result_sha256
        == canonical.traceability.canonical_result_sha256
    )

    assert (
        report.legal_decision.conclusion
        == report.analyzer.canonical_conclusion
    )


def test_g12_report_builder_does_not_mutate_sources() -> None:
    orchestration_request = _request()
    result = _orchestrator(None).run(
        orchestration_request
    )

    canonical = build_canonical_result(
        orchestration_request,
        result,
        now=_NOW,
    )

    analyzer = build_integral_legal_analysis(
        result
    )
    decision = build_legal_decision(
        analyzer
    )

    web_request = WebConsultationRequest(
        query=orchestration_request.query,
        mode=(
            orchestration_request
            .explanation_mode.value
        ),
        fiscal_year=(
            orchestration_request
            .query_fiscal_year
        ),
    )

    before_result = result.model_dump(mode="json")
    before_canonical = canonical.model_dump(mode="json")

    build_legal_consultation_report(
        web_request=web_request,
        orchestration_request=orchestration_request,
        result=result,
        canonical=canonical,
        analyzer=analyzer,
        legal_decision=decision,
    )

    assert result.model_dump(mode="json") == before_result
    assert (
        canonical.model_dump(mode="json")
        == before_canonical
    )


def test_g12_pdf_store_roundtrip(
    tmp_path: Path,
) -> None:
    _, _, _, report = _production_report()

    artifact = (
        build_legal_consultation_pdf_artifact(
            report
        )
    )

    path = save_web_legal_consultation_pdf_artifact(
        artifact,
        temp_root=tmp_path,
    )

    assert path.is_file()

    loaded = load_web_legal_consultation_pdf_artifact(
        artifact.execution_id,
        temp_root=tmp_path,
    )

    assert loaded == artifact
    assert loaded.pdf_bytes == artifact.pdf_bytes
    assert loaded.pdf_sha256 == artifact.pdf_sha256


def test_g12_pdf_store_rejects_invalid_execution_id(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        WebLegalConsultationPdfStoreError,
        match="Execution ID",
    ):
        load_web_legal_consultation_pdf_artifact(
            "../../etc/passwd",
            temp_root=tmp_path,
        )


def test_g12_pdf_store_rejects_tampered_pdf(
    tmp_path: Path,
) -> None:
    _, _, _, report = _production_report()

    artifact = (
        build_legal_consultation_pdf_artifact(
            report
        )
    )

    pdf_path = save_web_legal_consultation_pdf_artifact(
        artifact,
        temp_root=tmp_path,
    )

    original = pdf_path.read_bytes()

    tampered = (
        original[:-1]
        + bytes([original[-1] ^ 1])
    )

    pdf_path.write_bytes(tampered)

    with pytest.raises(
        WebLegalConsultationPdfStoreError,
        match="danado",
    ):
        load_web_legal_consultation_pdf_artifact(
            artifact.execution_id,
            temp_root=tmp_path,
        )
