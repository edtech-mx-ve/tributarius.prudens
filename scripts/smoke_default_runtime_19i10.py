from __future__ import annotations

import os

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.services.semantic_runtime_smoke import (
    DEFAULT_SMOKE_CASES,
    SemanticRuntimeSmokeError,
    assert_smoke_result,
    inspect_consultation_payload,
)
from app.web.dependencies import get_web_consultation_service


def _clear_runtime_override() -> None:
    os.environ.pop("RAG_ARTIFACT_DIR", None)
    get_settings.cache_clear()
    get_web_consultation_service.cache_clear()


def main() -> int:
    _clear_runtime_override()

    settings = get_settings()
    expected = "deployment/runtime_artifacts_semantic_v2"
    if settings.rag_artifact_dir != expected:
        print(
            "ERROR: el runtime por defecto no apunta a semantic_v2; "
            f"actual={settings.rag_artifact_dir}"
        )
        return 2

    from app.main import app

    client = TestClient(app)

    ready = client.get("/ready")
    if ready.status_code != 200:
        print(f"ERROR: /ready={ready.status_code}: {ready.text}")
        return 3

    health = client.get("/health")
    home = client.get("/")
    if health.status_code != 200 or home.status_code != 200:
        print(
            "ERROR: health/home no disponibles; "
            f"health={health.status_code}; home={home.status_code}"
        )
        return 4

    failures: list[str] = []
    for case in DEFAULT_SMOKE_CASES:
        response = client.post(
            "/api/v1/consultations",
            json={
                "query": case.query,
                "mode": "professional",
                "fiscal_year": case.fiscal_year,
            },
        )
        if response.status_code != 200:
            failures.append(f"{case.case_id}: HTTP {response.status_code}")
            continue
        try:
            result = inspect_consultation_payload(response.json(), case)
            assert_smoke_result(result)
        except SemanticRuntimeSmokeError as exc:
            failures.append(str(exc))
            continue
        print(
            f"case={result.case_id}; "
            f"expected={result.expected_document_id}; "
            f"found={result.primary_document_found}; "
            f"normative_refs={result.normative_reference_count}; "
            f"docs={','.join(result.returned_document_ids)}"
        )

    if failures:
        print("ERROR: runtime por defecto falló")
        for item in failures:
            print(f"- {item}")
        return 5

    print("OK: Sprint 19I.10; runtime semántico v2 es el default local")
    print(f"- rag_artifact_dir={settings.rag_artifact_dir}")
    print("- health=200")
    print("- home=200")
    print("- consultations=3/3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
