from __future__ import annotations

import argparse
import os
from pathlib import Path

from app.services.runtime_source_bridge_audit import (
    RuntimeSourceBridgeError,
    audit_runtime_source_bridge,
    write_runtime_source_bridge_report,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audita por SHA-256 el puente entre los chunks del runtime "
            "semántico v2 y los PDFs fuente del corpus local."
        )
    )
    parser.add_argument(
        "--corpus-dir",
        default=os.getenv("TRIBUTARIUS_CORPUS_DIR"),
        help=(
            "Directorio de PDFs fuente. También puede definirse con "
            "TRIBUTARIUS_CORPUS_DIR."
        ),
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not args.corpus_dir:
        print(
            "ERROR: indique --corpus-dir o defina TRIBUTARIUS_CORPUS_DIR."
        )
        return 2

    try:
        summary = audit_runtime_source_bridge(
            chunks_path=Path(
                "deployment/runtime_artifacts_semantic_v2/chunks.jsonl"
            ),
            content_policy_path=Path(
                "app/resources/runtime_publication_content_policy_19i18g.json"
            ),
            corpus_dir=Path(args.corpus_dir),
        )
        report = Path(
            "reports/sprint19I18I/runtime_source_bridge.json"
        )
        write_runtime_source_bridge_report(summary, report)
    except RuntimeSourceBridgeError as exc:
        print(f"ERROR: {exc}")
        return 2

    print("OK: Sprint 19I.18I; puente runtime -> PDF fuente auditado")
    print(f"- runtime_chunks={summary.runtime_chunks}")
    print(f"- candidate_documents={summary.candidate_documents}")
    print(
        "- verified_documents="
        + ",".join(summary.verified_documents)
    )
    print(
        "- blocked_documents="
        + ",".join(summary.blocked_documents)
    )
    print(
        "- missing_source_files="
        + ",".join(summary.missing_source_files)
    )
    print(
        "- hash_mismatch_documents="
        + ",".join(summary.hash_mismatch_documents)
    )
    print(f"- public_release_allowed={summary.public_release_allowed}")
    for item in summary.documents:
        print(
            f"  {item.document_id}: chunks={item.runtime_chunk_count}; "
            f"resolution_method={item.resolution_method}; "
            f"filename_match={item.filename_match}; "
            f"sha256_match={item.sha256_match}; "
            f"bridge_verified={item.bridge_verified}"
        )
    print(f"- report={report}")
    print(
        "POLICY: verificar que el runtime deriva byte-a-byte de los PDFs "
        "locales no demuestra todavía que esos PDFs procedan de una autoridad "
        "oficial. No se promueve ningún documento."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
