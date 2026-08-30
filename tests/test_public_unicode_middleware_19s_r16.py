from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.public_unicode_19s_r16 import PublicUnicodeNormalizationMiddleware


def _client() -> TestClient:
    app = FastAPI()
    app.add_middleware(PublicUnicodeNormalizationMiddleware)

    @app.get("/ready")
    def ready() -> dict[str, object]:
        return {
            "state": "ready",
            "capabilities": [
                {"detail": "Ãndice RAG presente."},
                {"detail": "PolÃtica jurÃdica disponible."},
            ],
        }

    @app.get("/unicode")
    def unicode_ok() -> dict[str, str]:
        return {"detail": "Política jurídica: México — IVA"}

    return TestClient(app)


def test_json_boundary_repairs_observed_mojibake() -> None:
    response = _client().get("/ready")
    assert response.status_code == 200
    assert response.json()["capabilities"] == [
        {"detail": "Índice RAG presente."},
        {"detail": "Política jurídica disponible."},
    ]


def test_json_boundary_preserves_valid_unicode_and_declares_charset() -> None:
    response = _client().get("/unicode")
    assert response.status_code == 200
    assert response.json()["detail"] == "Política jurídica: México — IVA"
    assert response.headers["content-type"].lower() == (
        "application/json; charset=utf-8"
    )
