from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.public_unicode_19s_r16 import PublicUnicodeNormalizationMiddleware


def _client() -> TestClient:
    app = FastAPI()
    app.add_middleware(PublicUnicodeNormalizationMiddleware)

    @app.get("/consult")
    def consult() -> dict[str, object]:
        return {
            "result": {
                "requires_human_review": True,
                "applicable_normative_refs": [],
                "evidence": [
                    {
                        "ref_id": "x",
                        "role": "normative",
                        "source_type": "normativa",
                        "title": "ResoluciÃ³n de prueba",
                    }
                ],
                "traceability": {
                    "events": [
                        {
                            "stage": "retrieval",
                            "requires_human_review": False,
                            "summary": "Chunks recuperados: 1.",
                        },
                        {
                            "stage": "normative",
                            "requires_human_review": False,
                            "summary": "Referencias normativas aplicables: 0.",
                        },
                    ]
                },
            }
        }

    return TestClient(app)


def test_boundary_reconciles_normative_trace_and_unicode() -> None:
    response = _client().get("/consult")
    assert response.status_code == 200
    result = response.json()["result"]

    assert result["requires_human_review"] is True
    assert result["applicable_normative_refs"] == []
    assert result["evidence"][0]["title"] == "Resolución de prueba"

    events = result["traceability"]["events"]
    assert events[0]["requires_human_review"] is False
    assert events[1]["stage"] == "normative"
    assert events[1]["requires_human_review"] is True
    assert "revisión humana" in events[1]["summary"]
