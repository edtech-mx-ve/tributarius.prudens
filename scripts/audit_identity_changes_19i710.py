from __future__ import annotations

import argparse
from pathlib import Path

from app.services.legal_identity_change_audit import (
    LegalIdentityChangeAuditError,
    audit_legal_identity_changes,
    write_legal_identity_change_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.7.10: explica los cambios de identidad de los "
            "14 residuos aún pendientes."
        )
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path("knowledge/chunks/chunks.jsonl"),
    )
    parser.add_argument(
        "--candidate",
        type=Path,
        default=Path("reports/sprint19I7/candidate_chunks.jsonl"),
    )
    parser.add_argument(
        "--normalized-root",
        type=Path,
        default=Path("knowledge/normalized/normativa"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/sprint19I710"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = audit_legal_identity_changes(
            baseline_path=args.baseline,
            candidate_path=args.candidate,
            normalized_root=args.normalized_root,
        )
        write_legal_identity_change_outputs(
            output_dir=args.output_dir,
            report=report,
        )
    except LegalIdentityChangeAuditError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("OK: Sprint 19I.7.10; cambios de identidad auditados")
    print(f"- total_identity_changed={report.total_identity_changed}")
    print(f"- resolved_safe={report.resolved_safe}")
    print(f"- requires_review={report.requires_review}")
    print("- classifications:")
    for key, value in report.classifications.items():
        print(f"  {key}={value}")
    print(f"- output_dir={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
