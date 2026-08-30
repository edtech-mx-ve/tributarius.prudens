from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.public_unicode_19s_r16 import (
    PublicUnicodeNormalizationMiddleware,
)


def test_middleware_attaches_integrity_after_evidence_cleanup() -> None:
    app = FastAPI()
    app.add_middleware(PublicUnicodeNormalizationMiddleware)

    @app.get("/sample")
    def sample() -> dict[str, object]:
        return {
            "result": {
                "explanation": "Respuesta de prueba basada en evidencia.",
                "requires_human_review": True,
                "applicable_normative_refs": [],
                "evidence": [
                    {"ref_id": "r1", "title": "ArtÃculo 1"},
                    {"ref_id": "r1", "title": "Duplicado"},
                ],
            }
        }

    response = TestClient(app).get("/sample")
    payload = response.json()
    result = payload["result"]

    assert len(result["evidence"]) == 1
    assert result["evidence"][0]["title"] == "Artículo 1"
    assert (
        result["explanation_integrity"]["status"]
        == "evidence_only_review_required"
    )
    assert result["explanation_integrity"]["evidence_count"] == 1
    assert result["explanation_integrity"]["llm_authority"] == "none"
