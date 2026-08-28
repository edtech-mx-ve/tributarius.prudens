from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from jurisprudence.assessment import assess_jurisprudential_candidate
from jurisprudence.loader import (
    JurisprudenceMetadataError,
    load_jurisprudence_metadata,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evalúa elegibilidad operativa de metadatos jurisprudenciales."
    )
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--query-date", type=date.fromisoformat, required=True)
    parser.add_argument("--norm-ref", action="append", default=[])
    parser.add_argument("--matter", type=str, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        records = load_jurisprudence_metadata(args.metadata)
    except JurisprudenceMetadataError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    assessments = [
        assess_jurisprudential_candidate(
            metadata,
            query_date=args.query_date,
            applicable_normative_refs=set(args.norm_ref),
            matter=args.matter,
        )
        for metadata in records.values()
    ]
    payload = {
        "candidate_count": len(assessments),
        "eligible_count": sum(item.eligible for item in assessments),
        "requires_human_review_count": sum(
            item.requires_human_review for item in assessments
        ),
        "assessments": [item.model_dump(mode="json") for item in assessments],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
