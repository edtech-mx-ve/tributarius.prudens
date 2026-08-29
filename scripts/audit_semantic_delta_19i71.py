from __future__ import annotations

import argparse
from pathlib import Path

from app.services.semantic_delta_audit import (
    SemanticDeltaAuditError,
    audit_semantic_delta,
    write_semantic_delta_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sprint 19I.7.1: auditoría causal del delta 19C -> 19I.7."
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
        default=Path("reports/sprint19I71"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = audit_semantic_delta(
            baseline_path=args.baseline,
            candidate_path=args.candidate,
        )
        write_semantic_delta_outputs(
            output_dir=args.output_dir,
            report=report,
        )
    except SemanticDeltaAuditError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("OK: Sprint 19I.7.1; auditoría causal completada")
    print(f"- baseline_chunks={report.baseline_chunks}")
    print(f"- candidate_chunks={report.candidate_chunks}")
    print(f"- exact_text_preserved={report.exact_text_preserved}")
    print(f"- removed_chunks={report.removed_chunks}")
    print(f"- added_chunks={report.added_chunks}")
    print("- removed_classifications:")
    for key, value in report.removed_classifications.items():
        print(f"  {key}={value}")
    print("- added_classifications:")
    for key, value in report.added_classifications.items():
        print(f"  {key}={value}")
    print(f"- output_dir={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
