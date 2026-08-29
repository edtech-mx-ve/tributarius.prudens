from __future__ import annotations

import argparse
from pathlib import Path

from app.services.semantic_source_residual_audit import (
    SemanticSourceResidualAuditError,
    audit_semantic_source_residuals,
    write_semantic_source_residual_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.7.9: contrasta los 21 residuos pendientes contra "
            "Markdown normalizado, parser actual e identidad candidata."
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
        default=Path("reports/sprint19I79"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = audit_semantic_source_residuals(
            baseline_path=args.baseline,
            candidate_path=args.candidate,
            normalized_root=args.normalized_root,
        )
        write_semantic_source_residual_outputs(
            output_dir=args.output_dir,
            report=report,
        )
    except SemanticSourceResidualAuditError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("OK: Sprint 19I.7.9; residuos contrastados contra fuente y parser")
    print(f"- total_requires_review={report.total_requires_review}")
    print(f"- resolved_safe={report.resolved_safe}")
    print(f"- still_requires_review={report.still_requires_review}")
    print("- classifications:")
    for key, value in report.classifications.items():
        print(f"  {key}={value}")
    print(f"- output_dir={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
