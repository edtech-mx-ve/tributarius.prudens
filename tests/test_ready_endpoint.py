from fastapi.testclient import TestClient

from app.main import app


def test_ready_endpoint_is_exposed() -> None:
    client = TestClient(app)
    response = client.get("/ready")

    assert response.status_code in {200, 503}
    payload = response.json()
    assert payload["service"] == "tributarius-prudens"
    assert payload["state"] in {"ready", "degraded", "not_ready"}
    assert isinstance(payload["capabilities"], list)
