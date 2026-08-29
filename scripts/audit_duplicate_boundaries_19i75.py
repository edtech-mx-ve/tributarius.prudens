from __future__ import annotations

import argparse
from pathlib import Path

from app.services.legal_duplicate_boundary_audit import (
    LegalDuplicateBoundaryAuditError,
    audit_duplicate_boundaries,
    write_duplicate_boundary_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.7.5: desambigua fronteras legales con etiquetas "
            "duplicadas mediante contenido y páginas."
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
        default=Path("reports/sprint19I75"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = audit_duplicate_boundaries(
            baseline_path=args.baseline,
            candidate_path=args.candidate,
        )
        write_duplicate_boundary_outputs(
            output_dir=args.output_dir,
            report=report,
        )
    except LegalDuplicateBoundaryAuditError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("OK: Sprint 19I.7.5; fronteras duplicadas auditadas")
    print(f"- total_ambiguous={report.total_ambiguous}")
    print(f"- resolved_unique_content={report.resolved_unique_content}")
    print(
        "- resolved_unique_page_overlap="
        f"{report.resolved_unique_page_overlap}"
    )
    print(f"- unresolved={report.unresolved}")
    print("- classifications:")
    for key, value in report.classifications.items():
        print(f"  {key}={value}")
    print(f"- output_dir={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
