from __future__ import annotations

import argparse
from pathlib import Path

from app.services.absorbed_numeric_audit import (
    AbsorbedNumericAuditError,
    audit_absorbed_numeric,
    write_absorbed_numeric_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.7.2: refina causalmente los 149 artículos numéricos "
            "absorbidos por el candidato 19I.7."
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
        default=Path("reports/sprint19I72"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = audit_absorbed_numeric(
            baseline_path=args.baseline,
            candidate_path=args.candidate,
        )
        write_absorbed_numeric_outputs(
            output_dir=args.output_dir,
            report=report,
        )
    except AbsorbedNumericAuditError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("OK: Sprint 19I.7.2; refinamiento numérico completado")
    print(f"- total_absorbed_numeric={report.total_absorbed_numeric}")
    print("- classifications:")
    for key, value in report.classifications.items():
        print(f"  {key}={value}")
    print(f"- output_dir={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
