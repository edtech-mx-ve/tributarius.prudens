from fastapi.testclient import TestClient

from app.main import app


def test_real_app_ready_json_declares_utf8_and_has_no_known_mojibake() -> None:
    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code in {200, 503}
    assert response.headers["content-type"].lower() == (
        "application/json; charset=utf-8"
    )
    text = response.content.decode("utf-8")
    assert "Ã" not in text
    assert "Â" not in text
    assert "â€" not in text


def test_real_app_health_contract_survives_unicode_middleware() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "tributarius-prudens"
