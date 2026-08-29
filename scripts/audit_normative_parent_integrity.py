from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path

from app.services.normative_integrity_audit import NormativeIntegrityAuditError
from app.services.normative_parent_audit import run_parent_audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.4: determina si los desalineamientos artículo↔texto "
            "provienen del chunk canónico 19C o de la segmentación 19F."
        )
    )
    parser.add_argument(
        "--retrieval",
        type=Path,
        default=Path("deployment/runtime_artifacts_19f/chunks.jsonl"),
    )
    parser.add_argument(
        "--canonical",
        type=Path,
        default=Path("knowledge/chunks/chunks.jsonl"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/sprint19I4"),
    )
    parser.add_argument(
        "--expected-retrieval-total",
        type=int,
        default=29402,
    )
    parser.add_argument(
        "--expected-canonical-total",
        type=int,
        default=3174,
    )
    return parser.parse_args()


def _summary_int(summary: Mapping[str, object], key: str) -> int:
    value = summary.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise NormativeIntegrityAuditError(
            f"Valor no entero en resumen para {key!r}: {value!r}"
        )
    return value


def main() -> int:
    args = parse_args()
    try:
        _, summary, outputs = run_parent_audit(
            retrieval_path=args.retrieval,
            canonical_path=args.canonical,
            output_dir=args.output_dir,
        )
    except NormativeIntegrityAuditError as exc:
        print(f"ERROR: {exc}")
        return 1

    retrieval_total = _summary_int(summary, "retrieval_chunks")
    canonical_total = _summary_int(summary, "canonical_chunks")

    if (
        args.expected_retrieval_total
        and retrieval_total != args.expected_retrieval_total
    ):
        print(
            "ERROR: cardinalidad retrieval inesperada: "
            f"esperados={args.expected_retrieval_total}, "
            f"encontrados={retrieval_total}."
        )
        return 1

    if (
        args.expected_canonical_total
        and canonical_total != args.expected_canonical_total
    ):
        print(
            "ERROR: cardinalidad canónica inesperada: "
            f"esperados={args.expected_canonical_total}, "
            f"encontrados={canonical_total}."
        )
        return 1

    print("OK: Sprint 19I.4; auditoría causal 19C↔19F completada")
    print(f"- retrieval_chunks={retrieval_total}")
    print(f"- normative_chunks={summary['normative_chunks']}")
    print(f"- canonical_chunks={canonical_total}")

    causal_counts = summary.get("causal_counts")
    if isinstance(causal_counts, dict):
        for key, value in sorted(causal_counts.items()):
            print(f"- {key}={value}")

    for label, path in outputs.items():
        print(f"- {label}={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
