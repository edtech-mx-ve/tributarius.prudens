from __future__ import annotations

import argparse
from pathlib import Path

from app.services.normative_temporal_evidence_audit import (
    NormativeTemporalEvidenceAuditError,
    audit_temporal_evidence,
    write_temporal_evidence_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.11: audita cobertura temporal del runtime semántico v2 "
            "y localiza evidencia textual candidata sin inferir vigencias."
        )
    )
    parser.add_argument(
        "--runtime-chunks",
        type=Path,
        default=Path("deployment/runtime_artifacts_semantic_v2/chunks.jsonl"),
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
        default=Path("reports/sprint19I11"),
    )
    parser.add_argument("--expected-total", type=int, default=29326)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    audit_dir = args.output_dir / "integrity"
    try:
        report = audit_temporal_evidence(
            runtime_chunks_path=args.runtime_chunks,
            normalized_root=args.normalized_root,
            catalog_path=args.catalog,
            audit_output_dir=audit_dir,
            expected_total_chunks=args.expected_total,
        )
        outputs = write_temporal_evidence_outputs(
            output_dir=args.output_dir,
            report=report,
        )
    except NormativeTemporalEvidenceAuditError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("OK: Sprint 19I.11; cobertura temporal auditada")
    print(f"- runtime_chunks={report.runtime_chunks}")
    print(f"- normative_chunks={report.normative_chunks}")
    print(f"- normative_documents={report.normative_documents}")
    print(f"- temporal_known={report.temporal_known}")
    print(f"- temporal_unknown={report.temporal_unknown}")
    print(f"- temporal_invalid={report.temporal_invalid}")
    print(f"- promotion_eligible={report.promotion_eligible}")
    print(
        "- priority_unknown_documents="
        + ",".join(report.priority_unknown_documents)
    )
    print(f"- evidence_lines={len(report.evidence_lines)}")
    print("- by_document:")
    for item in report.documents:
        print(
            f"  {item.canonical_id}: "
            f"chunks={item.normative_chunks}; "
            f"known={item.normative_chunks - item.temporal_unknown}; "
            f"unknown={item.temporal_unknown}; "
            f"eligible={item.promotion_eligible}; "
            f"status={item.status}"
        )
    for label, path in outputs.items():
        print(f"- {label}={path}")
    print(
        "POLICY: no se infirió effective_from/effective_to desde publicación "
        "ni última reforma."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
