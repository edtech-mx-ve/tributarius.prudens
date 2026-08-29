from __future__ import annotations

import argparse
from pathlib import Path

from app.services.legal_profile_boundary_audit import (
    LegalProfileBoundaryAuditError,
    audit_profile_boundaries,
    write_profile_boundary_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.7.11: reevalúa los 14 casos con el perfil real "
            "de chunking, no con detectores genéricos."
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
        "--catalog",
        type=Path,
        default=Path("app/resources/fiscal_corpus_15_catalog.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/sprint19I711"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = audit_profile_boundaries(
            baseline_path=args.baseline,
            candidate_path=args.candidate,
            normalized_root=args.normalized_root,
            catalog_path=args.catalog,
        )
        write_profile_boundary_outputs(
            output_dir=args.output_dir,
            report=report,
        )
    except LegalProfileBoundaryAuditError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("OK: Sprint 19I.7.11; fronteras reevaluadas con perfil real")
    print(f"- total_cases={report.total_cases}")
    print(f"- resolved_safe={report.resolved_safe}")
    print(f"- requires_review={report.requires_review}")
    print("- classifications:")
    for key, value in report.classifications.items():
        print(f"  {key}={value}")
    print(f"- output_dir={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
