from __future__ import annotations

import argparse
from pathlib import Path

from app.services.normative_temporal_priority_review import (
    NormativeTemporalPriorityReviewError,
    build_priority_review_report,
    load_priority_evidence,
    write_priority_review_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.12: prioriza evidencia temporal de LIVA/CPEUM "
            "sin promover fechas automáticamente."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("reports/sprint19I11/temporal_evidence_lines.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/sprint19I12"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        records, total_input = load_priority_evidence(input_csv=args.input)
        report = build_priority_review_report(
            records=records,
            total_input_lines=total_input,
        )
        outputs = write_priority_review_outputs(
            output_dir=args.output_dir,
            report=report,
        )
    except NormativeTemporalPriorityReviewError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("OK: Sprint 19I.12; evidencia temporal prioritaria clasificada")
    print(f"- total_input_lines={report.total_input_lines}")
    print(f"- total_priority_lines={report.total_priority_lines}")
    print(f"- liva_lines={report.liva_lines}")
    print(f"- cpeum_lines={report.cpeum_lines}")
    print(f"- strong_entry_into_force={report.strong_entry_into_force}")
    print(f"- effects_from_date={report.effects_from_date}")
    print(f"- transitory_context={report.transitory_context}")
    print(f"- publication_reference={report.publication_reference}")
    print(f"- generic_validity={report.generic_validity}")
    print(f"- unclassified={report.unclassified}")
    print(
        "- candidates_with_explicit_date_signal="
        f"{report.candidates_with_explicit_date_signal}"
    )
    print(f"- promotion_ready={report.promotion_ready}")
    for label, path in outputs.items():
        print(f"- {label}={path}")
    print(
        "POLICY: toda fecha detectada es solo candidata; "
        "requiere verificación antes de enriquecer metadatos."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
