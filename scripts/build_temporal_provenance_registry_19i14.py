from __future__ import annotations

import argparse
from pathlib import Path

from app.services.normative_temporal_provenance_registry import (
    NormativeTemporalProvenanceRegistryError,
    build_registry_from_verification,
    validate_fail_closed_registry,
    write_registry,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.14: construye registro versionado de procedencia temporal "
            "sin promover vigencias."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(
            "reports/sprint19I13/temporal_candidate_verification.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "knowledge/temporal/temporal_provenance_registry.json"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        registry = build_registry_from_verification(
            verification_report_path=args.input
        )
        validate_fail_closed_registry(registry)
        output = write_registry(output_path=args.output, registry=registry)
    except NormativeTemporalProvenanceRegistryError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("OK: Sprint 19I.14; registro temporal fail-closed generado")
    print(f"- schema_version={registry.schema_version}")
    print(f"- entries={len(registry.entries)}")
    print(f"- coverage_gaps={len(registry.coverage_gaps)}")
    print(
        "- blocked_scope_specific="
        f"{sum(e.promotion_status == 'blocked_scope_specific' for e in registry.entries)}"
    )
    human_review_count = sum(
        entry.promotion_status
        == "requires_human_verification_document_scope"
        for entry in registry.entries
    )
    print(
        "- requires_human_verification_document_scope="
        f"{human_review_count}"
    )
    for entry in registry.entries:
        print(
            f"  {entry.canonical_id}:{entry.source_line}; "
            f"date={entry.explicit_date_signal}; "
            f"scope={entry.scope_classification}; "
            f"promotion={entry.promotion_status}"
        )
    for gap in registry.coverage_gaps:
        print(
            f"  gap {gap.canonical_id}: "
            f"{gap.gap_type}; status={gap.status}"
        )
    print(f"- output={output}")
    print(
        "POLICY: effective_from/effective_to permanecen nulos; "
        "sin promoción automática de vigencia."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
