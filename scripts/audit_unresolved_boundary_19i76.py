from __future__ import annotations

import argparse
from pathlib import Path

from app.services.legal_unresolved_boundary_audit import (
    LegalUnresolvedBoundaryAuditError,
    audit_unresolved_boundaries,
    write_unresolved_boundary_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.7.6: inspecciona con evidencia completa las fronteras "
            "duplicadas que 19I.7.5 no pudo resolver."
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
        default=Path("reports/sprint19I76"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = audit_unresolved_boundaries(
            baseline_path=args.baseline,
            candidate_path=args.candidate,
        )
        write_unresolved_boundary_outputs(
            output_dir=args.output_dir,
            report=report,
        )
    except LegalUnresolvedBoundaryAuditError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("OK: Sprint 19I.7.6; caso(s) no resuelto(s) aislado(s)")
    print(f"- total_unresolved={report.total_unresolved}")
    for finding in report.findings:
        print(
            f"- baseline={finding.baseline_chunk_id}; "
            f"document={finding.canonical_id}; "
            f"label={finding.baseline_unit_label}; "
            f"pages={finding.baseline_page_start}-{finding.baseline_page_end}; "
            f"class={finding.classification}"
        )
        for evidence in finding.candidate_evidence:
            print(
                "  candidate="
                f"{evidence.chunk_id}; "
                f"pages={evidence.page_start}-{evidence.page_end}; "
                f"contains_baseline={evidence.contains_baseline_text}; "
                f"baseline_contains_candidate="
                f"{evidence.baseline_contains_candidate_text}; "
                f"shared_prefix_chars={evidence.shared_prefix_chars}"
            )
    print(f"- output_dir={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
