from fastapi.testclient import TestClient

from app.main import app
from app.web.dependencies import get_web_consultation_service
from app.web.schemas import WebConsultationRequest
from app.web.service import WebConsultationService

client = TestClient(app)


def test_home_renders_semantic_interface() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Tributarius prudens" in response.text
    assert 'id="consultation-form"' in response.text
    assert 'href="#main-content"' in response.text
    assert "No incluyas RFC" in response.text


def test_static_assets_are_served() -> None:
    css = client.get("/static/css/app.css")
    javascript = client.get("/static/js/app.js")
    assert css.status_code == 200
    assert javascript.status_code == 200
    assert "@media" in css.text
    assert "fetch(" in javascript.text


def test_consultation_validates_payload() -> None:
    response = client.post(
        "/api/v1/consultations",
        json={"query": "x", "mode": "taxpayer"},
    )
    assert response.status_code == 422


def test_consultation_does_not_fake_backend_result() -> None:
    app.dependency_overrides[get_web_consultation_service] = lambda: (
        WebConsultationService()
    )
    try:
        response = client.post(
            "/api/v1/consultations",
            json={
                "query": "¿Qué obligaciones debo revisar?",
                "mode": "taxpayer",
                "fiscal_year": 2026,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "not_configured"
    assert payload["result"] is None


class FakeRunner:
    def run(self, request: WebConsultationRequest) -> dict[str, object]:
        return {
            "folio": "TP-TEST",
            "mode": request.mode,
            "requires_human_review": False,
        }


def test_consultation_uses_injected_runner() -> None:
    app.dependency_overrides[get_web_consultation_service] = lambda: (
        WebConsultationService(FakeRunner())
    )
    try:
        response = client.post(
            "/api/v1/consultations",
            json={
                "query": "Consulta fiscal de prueba",
                "mode": "professional",
                "fiscal_year": 2026,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["result"]["folio"] == "TP-TEST"
