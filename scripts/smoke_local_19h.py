from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.config import Settings
from app.services.runtime_factory import RuntimeBuildError, build_runtime_components
from app.web.schemas import WebConsultationRequest


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Smoke local Sprint 19H: web -> orchestrador -> RAG 19G -> traza."
    )
    value.add_argument(
        "--index-dir",
        type=Path,
        default=Path("deployment/runtime_artifacts_19f"),
    )
    value.add_argument(
        "--query",
        default="Ley del IVA tasa general del impuesto al valor agregado",
    )
    value.add_argument("--fiscal-year", type=int, default=2026)
    value.add_argument("--local-files-only", action="store_true")
    return value


def main() -> int:
    args = parser().parse_args()
    settings = Settings(
        _env_file=None,
        rag_artifact_dir=str(args.index_dir),
        rag_local_files_only=args.local_files_only,
    )
    try:
        components = build_runtime_components(settings)
        result = components.runner.run(
            WebConsultationRequest(
                query=args.query,
                mode="professional",
                fiscal_year=args.fiscal_year,
            )
        )
    except RuntimeBuildError as exc:
        print(f"ERROR: {exc}")
        return 2

    evidence = result.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        print("ERROR: el runtime no devolvió evidencia RAG.")
        return 3

    document_sources = [
        item
        for item in evidence
        if isinstance(item, dict) and item.get("kind") == "document"
    ]
    if not document_sources:
        print("ERROR: la traza no contiene documentos recuperados.")
        return 4

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    print(
        "OK: integración 19H operativa; "
        f"evidence={len(document_sources)}; model={components.model_name}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
