from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.routes import web as web_routes
from app.domain.legal_consultation_pdf_artifact import (
    LegalConsultationPdfArtifact,
)
from app.services.legal_consultation_pdf_artifact import (
    build_legal_consultation_pdf_artifact,
)
from app.web.runtime_runner import WebHybridRunner
from app.web.schemas import WebConsultationRequest
from tests.test_block12_4_hypothesis_verification import (
    _orchestrator,
    _request,
)
from tests.test_block_g12_pdf_endpoint_foundation import (
    _production_report,
)


def _web_request() -> WebConsultationRequest:
    request = _request()

    return WebConsultationRequest(
        query=request.query,
        mode=request.explanation_mode.value,
        fiscal_year=request.query_fiscal_year,
    )


def test_g12_runtime_generates_pdf_from_same_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[LegalConsultationPdfArtifact] = []

    def fake_save(
        artifact: LegalConsultationPdfArtifact,
    ) -> Path:
        captured.append(artifact)
        return Path("unused.pdf")

    monkeypatch.setattr(
        "app.web.runtime_runner."
        "save_web_legal_consultation_pdf_artifact",
        fake_save,
    )

    runner = WebHybridRunner(
        orchestrator=_orchestrator(None),
        retrieval_runtime="test",
        explanation_runtime="test",
        hybrid_llama_runtime=None,
    )

    presented = runner.run(_web_request())

    assert len(captured) == 1

    artifact = captured[0]

    trace = presented["traceability"]
    assert isinstance(trace, dict)

    assert (
        artifact.execution_id
        == trace["execution_id"]
    )

    pdf = presented["pdf"]
    assert isinstance(pdf, dict)

    assert pdf["execution_id"] == artifact.execution_id
    assert pdf["sha256"] == artifact.pdf_sha256
    assert pdf["filename"] == artifact.filename
    assert (
        pdf["content_length"]
        == artifact.content_length
    )

    assert pdf["download_path"] == (
        f"/api/v1/consultations/"
        f"{artifact.execution_id}/pdf"
    )


def test_g12_pdf_endpoint_returns_exact_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, _, report = _production_report()

    artifact = (
        build_legal_consultation_pdf_artifact(
            report
        )
    )

    calls: list[str] = []

    def fake_load(
        execution_id: str,
    ) -> LegalConsultationPdfArtifact:
        calls.append(execution_id)
        return artifact

    monkeypatch.setattr(
        web_routes,
        "load_web_legal_consultation_pdf_artifact",
        fake_load,
    )

    response = web_routes.download_consultation_pdf(
        artifact.execution_id
    )

    assert calls == [artifact.execution_id]
    assert response.status_code == 200
    assert response.body == artifact.pdf_bytes
    assert response.media_type == "application/pdf"

    assert (
        response.headers["content-disposition"]
        == f'attachment; filename="{artifact.filename}"'
    )

    assert (
        response.headers["x-content-sha256"]
        == artifact.pdf_sha256
    )

    assert (
        response.headers[
            "x-canonical-result-sha256"
        ]
        == artifact.source_canonical_result_sha256
    )

    assert (
        response.headers["content-length"]
        == str(artifact.content_length)
    )

    assert (
        response.headers["cache-control"]
        == "private, no-store"
    )


def test_g12_pdf_endpoint_returns_404_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_load(
        execution_id: str,
    ) -> LegalConsultationPdfArtifact:
        raise web_routes.WebLegalConsultationPdfStoreError(
            "El PDF no esta disponible."
        )

    monkeypatch.setattr(
        web_routes,
        "load_web_legal_consultation_pdf_artifact",
        fake_load,
    )

    with pytest.raises(HTTPException) as exc:
        web_routes.download_consultation_pdf(
            "TP-" + ("A" * 32)
        )

    assert exc.value.status_code == 404


def test_g12_pdf_get_route_is_registered() -> None:
    matching = [
        route
        for route in web_routes.router.routes
        if getattr(route, "path", None)
        == "/api/v1/consultations/{execution_id}/pdf"
    ]

    assert len(matching) == 1

    methods = getattr(
        matching[0],
        "methods",
        set(),
    )

    assert "GET" in methods
