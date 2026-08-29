from __future__ import annotations

import argparse
from pathlib import Path

from app.services.legal_boundary_identity_audit import (
    LegalBoundaryIdentityAuditError,
    audit_boundary_identity,
    write_boundary_identity_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.7.4: verifica si las 135 fronteras legítimas siguen "
            "existiendo por identidad documental y etiqueta, aunque cambie el texto."
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
        "--output-dir",
        type=Path,
        default=Path("reports/sprint19I74"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = audit_boundary_identity(
            baseline_path=args.baseline,
            candidate_path=args.candidate,
        )
        write_boundary_identity_outputs(
            output_dir=args.output_dir,
            report=report,
        )
    except LegalBoundaryIdentityAuditError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("OK: Sprint 19I.7.4; identidad de fronteras auditada")
    print(f"- total_probable_legitimate={report.total_probable_legitimate}")
    print(
        "- preserved_boundary_identity="
        f"{report.preserved_boundary_identity}"
    )
    print(f"- missing_boundary_identity={report.missing_boundary_identity}")
    print(
        "- ambiguous_boundary_identity="
        f"{report.ambiguous_boundary_identity}"
    )
    print("- classifications:")
    for key, value in report.classifications.items():
        print(f"  {key}={value}")
    print(f"- output_dir={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
