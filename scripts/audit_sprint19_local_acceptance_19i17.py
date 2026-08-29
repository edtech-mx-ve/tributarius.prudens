from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from app.services.sprint19_local_acceptance_audit import (
    Sprint19LocalAcceptanceError,
    Sprint19LocalAcceptancePaths,
    audit_sprint19_local_acceptance,
    summary_as_dict,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.17: audita los artefactos críticos del cierre local "
            "sin modificar corpus, FAISS ni metadatos."
        )
    )
    parser.add_argument(
        "--semantic-corpus",
        type=Path,
        default=Path("knowledge/chunks/chunks_semantic_v2.jsonl"),
    )
    parser.add_argument(
        "--semantic-manifest",
        type=Path,
        default=Path("knowledge/chunks/chunks_semantic_v2_manifest.json"),
    )
    parser.add_argument(
        "--runtime-dir",
        type=Path,
        default=Path("deployment/runtime_artifacts_semantic_v2"),
    )
    parser.add_argument(
        "--temporal-registry",
        type=Path,
        default=Path("knowledge/temporal/temporal_provenance_registry.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/sprint19I17/local_acceptance_audit.json"),
    )
    return parser.parse_args()


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        delete=False,
        dir=resolved.parent,
        prefix=f".{resolved.name}.",
        suffix=".tmp",
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    try:
        os.replace(temporary, resolved)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> int:
    args = parse_args()
    try:
        summary = audit_sprint19_local_acceptance(
            paths=Sprint19LocalAcceptancePaths(
                semantic_corpus=args.semantic_corpus,
                semantic_manifest=args.semantic_manifest,
                runtime_dir=args.runtime_dir,
                temporal_registry=args.temporal_registry,
            )
        )
    except Sprint19LocalAcceptanceError as exc:
        print(f"ERROR: {exc}")
        return 1

    payload = summary_as_dict(summary)
    _atomic_json(args.output, payload)

    print("OK: Sprint 19I.17; auditoría integral local ejecutada")
    print(f"- semantic_status={summary.semantic_status}")
    print(f"- semantic_parent_chunks={summary.semantic_parent_chunks}")
    print(f"- semantic_document_count={summary.semantic_document_count}")
    print(f"- runtime_chunk_count={summary.runtime_chunk_count}")
    print(f"- runtime_vector_dimension={summary.runtime_vector_dimension}")
    print(f"- runtime_model_name={summary.runtime_model_name}")
    print(
        "- temporal_blocked_documents="
        f"{','.join(summary.temporal_blocked_documents)}"
    )
    print(f"- temporal_entries={summary.temporal_entry_count}")
    print(f"- temporal_coverage_gaps={summary.temporal_coverage_gap_count}")
    print(f"- default_runtime_dir={summary.default_runtime_dir}")
    print(f"- failures={len(summary.failures)}")
    print(f"- report={args.output}")

    if summary.failures:
        for failure in summary.failures:
            print(f"  FAIL: {failure}")
        return 2

    print(
        "POLICY: cierre técnico local no equivale a completitud jurídica; "
        "la vigencia desconocida continúa fail-closed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
