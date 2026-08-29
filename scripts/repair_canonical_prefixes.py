from __future__ import annotations

import argparse
from pathlib import Path

from app.services.canonical_prefix_repair import (
    apply_prefix_repair,
    build_prefix_repair_plan,
    write_plan,
)
from app.services.normative_integrity_audit import NormativeIntegrityAuditError

DEFAULT_CANDIDATES = (
    "cff:article:articulo-31:00019:ef7afb6b73be4523",
    "liva:article:articulo-18:00049:47d0365fe043a858",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.6: sanea prefijos contaminantes antes del encabezado "
            "legal que coincide con la metadata del chunk canónico."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("knowledge/chunks/chunks.jsonl"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("knowledge/chunks/chunks_19i6_repaired.jsonl"),
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path("reports/sprint19I6/canonical_prefix_repair_plan.json"),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Escribe una copia reparada en --output; nunca sobrescribe --input.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.apply:
            plan = apply_prefix_repair(
                input_path=args.input,
                output_path=args.output,
                candidate_chunk_ids=DEFAULT_CANDIDATES,
            )
        else:
            plan = build_prefix_repair_plan(
                input_path=args.input,
                candidate_chunk_ids=DEFAULT_CANDIDATES,
            )
        write_plan(args.plan, plan)
    except NormativeIntegrityAuditError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("OK: Sprint 19I.6; análisis de reparación canónica completado")
    print(f"- input={args.input}")
    print(f"- total_chunks={plan.total_chunks}")
    print(f"- candidates={len(plan.findings)}")
    for finding in plan.findings:
        print(
            f"- {finding.document_id}: chunk={finding.chunk_id}; "
            f"repairable={finding.repairable}; "
            f"reason={finding.reason}; "
            f"prefix_chars={finding.prefix_chars}; "
            f"metadata_article={finding.metadata_article}; "
            f"first_heading={finding.first_heading_article}"
        )
    print(f"- plan={args.plan}")
    print(f"- output={args.output}" if args.apply else "- mode=dry-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
