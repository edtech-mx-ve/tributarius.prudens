from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from app.services.legal_heading_source_audit import (
    LegalHeadingSourceAuditError,
    audit_heading_sources,
    write_heading_source_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.7.3: contrasta los 135 artículos probablemente legítimos "
            "contra sus líneas exactas en Markdown normalizado."
        )
    )
    parser.add_argument("--project-root", type=Path, default=Path("."))
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
        default=Path("reports/sprint19I73"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = audit_heading_sources(
            project_root=args.project_root,
            baseline_path=args.baseline,
            candidate_path=args.candidate,
        )
        write_heading_source_outputs(
            output_dir=args.output_dir,
            report=report,
        )
    except LegalHeadingSourceAuditError as exc:
        print(f"ERROR: {exc}")
        return 1

    counts = Counter(item.classification for item in report.findings)
    print("OK: Sprint 19I.7.3; auditoría fuente↔parser completada")
    print(f"- total_probable_legitimate={report.total_probable_legitimate}")
    print(f"- markdown_match_found={report.markdown_match_found}")
    print(f"- parser_matches_source_line={report.parser_matches_source_line}")
    print(f"- parser_misses_source_line={report.parser_misses_source_line}")
    print("- classifications:")
    for key, value in sorted(counts.items()):
        print(f"  {key}={value}")
    print(f"- output_dir={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
