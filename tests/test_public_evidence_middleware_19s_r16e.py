from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.public_unicode_19s_r16 import (
    PublicUnicodeNormalizationMiddleware,
)


def test_middleware_cleans_visible_evidence_without_changing_review() -> None:
    app = FastAPI()
    app.add_middleware(PublicUnicodeNormalizationMiddleware)

    @app.get("/sample")
    def sample() -> dict[str, object]:
        return {
            "result": {
                "requires_human_review": True,
                "evidence": [
                    {
                        "ref_id": "r1",
                        "document_id": "liva",
                        "title": "ArtÃculo 1",
                        "snippet": "Texto",
                    },
                    {
                        "ref_id": "r1",
                        "document_id": "liva",
                        "title": "Duplicado",
                        "snippet": "Texto",
                    },
                    {},
                ],
            }
        }

    response = TestClient(app).get("/sample")
    payload = response.json()

    assert response.status_code == 200
    assert payload["result"]["requires_human_review"] is True
    assert payload["result"]["evidence"] == [
        {
            "ref_id": "r1",
            "document_id": "liva",
            "title": "Artículo 1",
            "snippet": "Texto",
        }
    ]
