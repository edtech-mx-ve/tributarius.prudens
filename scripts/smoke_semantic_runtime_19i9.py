from __future__ import annotations

import argparse
import os
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.services.semantic_runtime_smoke import (
    DEFAULT_SMOKE_CASES,
    SemanticRuntimeSmokeError,
    assert_smoke_result,
    inspect_consultation_payload,
)
from app.web.dependencies import get_web_consultation_service


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.9: activa en este proceso el runtime semántico v2 "
            "y ejecuta smokes E2E LIVA/CPEUM/LIEPS."
        )
    )
    parser.add_argument(
        "--index-dir",
        type=Path,
        default=Path("deployment/runtime_artifacts_semantic_v2"),
    )
    parser.add_argument("--local-files-only", action="store_true")
    return parser.parse_args()


def _configure_process(index_dir: Path, *, local_files_only: bool) -> None:
    resolved = index_dir.expanduser().resolve()
    os.environ["RAG_ARTIFACT_DIR"] = str(resolved)
    os.environ["REQUIRE_RAG_ARTIFACTS"] = "true"
    os.environ["VERIFY_RAG_INTEGRITY"] = "true"
    os.environ["RAG_LOCAL_FILES_ONLY"] = "true" if local_files_only else "false"
    get_settings.cache_clear()
    get_web_consultation_service.cache_clear()


def main() -> int:
    args = parse_args()
    _configure_process(
        args.index_dir,
        local_files_only=args.local_files_only,
    )

    # Importar después de configurar el proceso garantiza que app.main
    # use los artefactos semánticos v2 durante este smoke.
    from app.main import app

    client = TestClient(app)

    ready = client.get("/ready")
    if ready.status_code != 200:
        print(f"ERROR: /ready respondió {ready.status_code}: {ready.text}")
        return 2
    ready_payload = ready.json()
    print(
        "ready: "
        f"state={ready_payload.get('state')}; "
        f"capabilities={ready_payload.get('capabilities')}"
    )

    health = client.get("/health")
    if health.status_code != 200:
        print(f"ERROR: /health respondió {health.status_code}")
        return 3

    home = client.get("/")
    if home.status_code != 200:
        print(f"ERROR: / respondió {home.status_code}")
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
            failures.append(
                f"{case.case_id}: HTTP {response.status_code}"
            )
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
            f"evidence={result.evidence_count}; "
            f"normative_refs={result.normative_reference_count}; "
            f"jurisprudence={result.jurisprudence_count}; "
            f"docs={','.join(result.returned_document_ids)}"
        )

    if failures:
        print("ERROR: smoke semántico falló")
        for item in failures:
            print(f"- {item}")
        return 5

    print("OK: Sprint 19I.9; runtime semántico v2 operativo E2E en local")
    print(f"- index_dir={args.index_dir.expanduser().resolve()}")
    print("- health=200")
    print("- home=200")
    print("- consultations=3/3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
