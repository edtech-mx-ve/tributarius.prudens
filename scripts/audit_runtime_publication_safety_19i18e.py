from __future__ import annotations

import argparse
from pathlib import Path

from app.services.runtime_publication_safety_audit import (
    RuntimePublicationSafetyError,
    audit_runtime_publication_safety,
    write_publication_safety_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.18E: audita si el runtime puede publicarse "
            "sin asumir permisos de redistribución."
        )
    )
    parser.add_argument(
        "--chunks",
        type=Path,
        default=Path(
            "deployment/runtime_artifacts_semantic_v2/chunks.jsonl"
        ),
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path(
            "app/resources/runtime_publication_policy_19i18e.json"
        ),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(
            "reports/sprint19I18E/runtime_publication_safety.json"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = audit_runtime_publication_safety(
            chunks_path=args.chunks,
            policy_path=args.policy,
        )
        write_publication_safety_report(summary, args.report)
    except RuntimePublicationSafetyError as exc:
        print(f"ERROR: {exc}")
        return 2

    print("OK: Sprint 19I.18E; seguridad de publicación auditada")
    print(f"- runtime_chunks={summary.runtime_chunks}")
    print(f"- observed_documents={summary.observed_documents}")
    print(f"- policy_documents={summary.policy_documents}")
    print(f"- verified_documents={summary.verified_documents}")
    print(f"- blocked_documents={summary.blocked_documents}")
    print(
        f"- missing_policy_documents={summary.missing_policy_documents}"
    )
    print(
        f"- public_release_allowed={summary.public_release_allowed}"
    )
    for result in summary.results:
        print(
            f"  {result.document_id}: chunks={result.chunk_count}; "
            f"text_bytes={result.text_bytes}; "
            f"status={result.redistribution_status}; "
            f"publishable={result.publishable}"
        )
    print(f"- report={args.report}")
    print(
        "POLICY: ningún documento se considera redistribuible por inferencia. "
        "Solo public_redistribution_verified con evidencia explícita habilita "
        "un release público."
    )
    return 0 if summary.public_release_allowed else 3


if __name__ == "__main__":
    raise SystemExit(main())
