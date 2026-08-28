from datetime import date

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_normative_route_is_registered() -> None:
    paths = app.openapi()["paths"]
    assert "/normative/legal-units/{legal_unit_id}/applicable" in paths


def test_normative_route_validates_fiscal_year() -> None:
    response = client.get(
        "/normative/legal-units/1/applicable",
        params={"query_date": date(2026, 8, 27).isoformat(), "fiscal_year": 1800},
    )
    assert response.status_code == 422
