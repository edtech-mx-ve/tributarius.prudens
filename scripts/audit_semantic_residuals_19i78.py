from __future__ import annotations

import argparse
from pathlib import Path

from app.services.semantic_residual_audit import (
    SemanticResidualAuditError,
    audit_semantic_residuals,
    write_semantic_residual_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.7.8: consolida los residuos semánticos aún no "
            "cerrados antes de promover el candidato 19I.7."
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
        default=Path("reports/sprint19I78"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = audit_semantic_residuals(
            baseline_path=args.baseline,
            candidate_path=args.candidate,
        )
        write_semantic_residual_outputs(
            output_dir=args.output_dir,
            report=report,
        )
    except SemanticResidualAuditError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("OK: Sprint 19I.7.8; residuos semánticos consolidados")
    print(f"- total_residuals={report.total_residuals}")
    print(f"- safe_absorptions={report.safe_absorptions}")
    print(f"- requires_review={report.requires_review}")
    print("- classifications:")
    for key, value in report.classifications.items():
        print(f"  {key}={value}")
    print(f"- output_dir={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
