from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.api.routes import web as web_route
from app.domain.jurisprudence_document import (
    JurisprudenceDocumentRepresentation,
    JurisprudencePage,
)
from app.domain.jurisprudence_extraction import JurisprudenceExtractedMetadata
from app.main import app
from app.web.dependencies import get_web_consultation_service
from app.web.schemas import WebConsultationRequest, WebConsultationResponse

SESSION_ID = "a" * 32
DOCUMENT_ID = "jurisprudencia-e2e"
SHA256 = "b" * 64


class FakeWebService:
    def __init__(self) -> None:
        self.requests: list[WebConsultationRequest] = []

    def consult(self, request: WebConsultationRequest) -> WebConsultationResponse:
        self.requests.append(request)
        evidence: list[dict[str, object]] = []
        if request.jurisprudence_session_id is not None:
            evidence.append(
                {
                    "ref_id": (
                        "session-jurisprudence:"
                        f"{DOCUMENT_ID}:page:1"
                    ),
                    "kind": "jurisprudence",
                    "role": "jurisprudence",
                    "source_type": "jurisprudencia",
                    "source_label": "Jurisprudencia temporal",
                    "source_reference": "criterio.pdf",
                    "document_id": DOCUMENT_ID,
                    "page_start": 1,
                    "page_end": 1,
                    "score": 1.0,
                    "snippet": "Devolución conforme al artículo 22 del CFF.",
                }
            )

        return WebConsultationResponse(
            status="ready",
            message="Consulta procesada.",
            result={
                "mode": request.mode,
                "applicable_normative_refs": ["CFF:22"],
                "explanation": "Explicación controlada de prueba.",
                "evidence": evidence,
                "requires_human_review": bool(evidence),
            },
        )


def _representation() -> JurisprudenceDocumentRepresentation:
    text = "Devolución conforme al artículo 22 del CFF."
    return JurisprudenceDocumentRepresentation(
        document_id=DOCUMENT_ID,
        original_filename="criterio.pdf",
        source_sha256=SHA256,
        page_count=1,
        extracted_characters=len(text),
        pages=[
            JurisprudencePage(
                number=1,
                text=text,
                has_extractable_text=True,
            )
        ],
        full_text=text,
    )


def _metadata() -> JurisprudenceExtractedMetadata:
    return JurisprudenceExtractedMetadata(
        identifier="20260001",
        title="DEVOLUCIÓN DE SALDO A FAVOR.",
        court_or_body="Primera Sala",
        matter="fiscal",
        related_normative_refs=["CFF:22"],
        source_pages=[1],
        requires_human_review=True,
    )


def _client(service: FakeWebService) -> TestClient:
    app.dependency_overrides[get_web_consultation_service] = lambda: service
    return TestClient(app)


def test_e2e_home_exposes_llama_mode_and_jurisprudence_upload() -> None:
    service = FakeWebService()
    client = _client(service)
    try:
        response = client.get("/")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert 'id="jurisprudence-pdf"' in response.text
    assert '<option value="student">Estudiante</option>' in response.text
    assert '<option value="professional">Profesional</option>' in response.text
    assert '<option value="taxpayer">' not in response.text


def test_e2e_upload_pdf_returns_temporal_session(
    monkeypatch: Any,
) -> None:
    service = FakeWebService()
    client = _client(service)

    monkeypatch.setattr(
        web_route,
        "process_web_jurisprudence_upload",
        lambda **kwargs: (SESSION_ID, _representation(), _metadata()),
    )

    try:
        response = client.post(
            "/api/v1/jurisprudence/session",
            content=b"%PDF-1.4 e2e",
            headers={
                "Content-Type": "application/pdf",
                "X-Filename": "criterio.pdf",
                "Origin": "http://testserver",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["session_id"] == SESSION_ID
    assert payload["document_id"] == DOCUMENT_ID
    assert payload["filename"] == "criterio.pdf"
    assert payload["page_count"] == 1


def test_e2e_uploaded_session_reaches_consultation_and_evidence() -> None:
    service = FakeWebService()
    client = _client(service)

    try:
        response = client.post(
            "/api/v1/consultations",
            json={
                "query": "¿Procede la devolución del saldo a favor?",
                "mode": "professional",
                "fiscal_year": 2026,
                "jurisprudence_session_id": SESSION_ID,
            },
            headers={"Origin": "http://testserver"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert service.requests[-1].jurisprudence_session_id == SESSION_ID
    assert service.requests[-1].mode == "professional"

    result = payload["result"]
    assert result["applicable_normative_refs"] == ["CFF:22"]
    assert result["requires_human_review"] is True
    assert result["evidence"][0]["role"] == "jurisprudence"
    assert result["evidence"][0]["document_id"] == DOCUMENT_ID


def test_e2e_student_and_professional_preserve_same_legal_result() -> None:
    service = FakeWebService()
    client = _client(service)

    try:
        student = client.post(
            "/api/v1/consultations",
            json={
                "query": "¿Procede la devolución del saldo a favor?",
                "mode": "student",
                "fiscal_year": 2026,
                "jurisprudence_session_id": SESSION_ID,
            },
            headers={"Origin": "http://testserver"},
        ).json()
        professional = client.post(
            "/api/v1/consultations",
            json={
                "query": "¿Procede la devolución del saldo a favor?",
                "mode": "professional",
                "fiscal_year": 2026,
                "jurisprudence_session_id": SESSION_ID,
            },
            headers={"Origin": "http://testserver"},
        ).json()
    finally:
        app.dependency_overrides.clear()

    assert student["result"]["mode"] == "student"
    assert professional["result"]["mode"] == "professional"
    assert (
        student["result"]["applicable_normative_refs"]
        == professional["result"]["applicable_normative_refs"]
        == ["CFF:22"]
    )
    assert student["result"]["evidence"] == professional["result"]["evidence"]


def test_e2e_consultation_without_pdf_still_works() -> None:
    service = FakeWebService()
    client = _client(service)

    try:
        response = client.post(
            "/api/v1/consultations",
            json={
                "query": "¿Qué debo revisar para una devolución?",
                "mode": "professional",
                "fiscal_year": 2026,
            },
            headers={"Origin": "http://testserver"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    result = response.json()["result"]
    assert service.requests[-1].jurisprudence_session_id is None
    assert result["evidence"] == []
    assert result["applicable_normative_refs"] == ["CFF:22"]


def test_e2e_cross_origin_upload_is_rejected(
    monkeypatch: Any,
) -> None:
    service = FakeWebService()
    client = _client(service)
    monkeypatch.setattr(
        web_route,
        "process_web_jurisprudence_upload",
        lambda **kwargs: (SESSION_ID, _representation(), _metadata()),
    )

    try:
        response = client.post(
            "/api/v1/jurisprudence/session",
            content=b"%PDF-1.4 e2e",
            headers={
                "Content-Type": "application/pdf",
                "X-Filename": "criterio.pdf",
                "Origin": "https://evil.example",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
