from __future__ import annotations

import argparse
from pathlib import Path

from app.core.config import Settings
from app.services.runtime_factory import (
    RuntimeBuildError,
    build_runtime_components,
)
from app.web.schemas import WebConsultationRequest

_QUERIES = (
    ("liva_tasa", "¿Cuál es la tasa general del IVA y cuál es su fundamento?"),
    (
        "cpeum_principios",
        "¿Qué principios constitucionales limitan la creación y cobro "
        "de contribuciones en México?",
    ),
    (
        "lieps",
        "¿Qué regula la Ley del IEPS y cuál es su fundamento legal?",
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diagnóstico directo del runtime semántico Sprint 19I.9."
    )
    parser.add_argument(
        "--index-dir",
        type=Path,
        default=Path("deployment/runtime_artifacts_semantic_v2"),
    )
    parser.add_argument("--local-files-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = Settings(
        _env_file=None,
        rag_artifact_dir=str(args.index_dir),
        rag_local_files_only=args.local_files_only,
        require_rag_artifacts=True,
        verify_rag_integrity=True,
    )
    try:
        components = build_runtime_components(settings)
    except RuntimeBuildError as exc:
        print(f"ERROR: runtime build: {exc}")
        return 2

    failures = 0
    for case_id, query in _QUERIES:
        try:
            result = components.runner.run(
                WebConsultationRequest(
                    query=query,
                    mode="professional",
                    fiscal_year=2026,
                )
            )
        except Exception as exc:
            failures += 1
            print(
                f"case={case_id}; ERROR={type(exc).__name__}: {exc}"
            )
            continue

        evidence = result.get("evidence")
        docs = []
        if isinstance(evidence, list):
            docs = [
                str(item.get("document_id"))
                for item in evidence
                if isinstance(item, dict)
                and item.get("kind") == "document"
            ]
        normative_refs = result.get("applicable_normative_refs")
        normative_count = (
            len(normative_refs)
            if isinstance(normative_refs, list)
            else 0
        )
        print(
            f"case={case_id}; status=ready; "
            f"docs={','.join(docs)}; "
            f"normative_refs={normative_count}"
        )

    if failures:
        print(f"ERROR: diagnosis failures={failures}")
        return 3
    print("OK: diagnóstico directo 19I.9 sin excepciones")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
