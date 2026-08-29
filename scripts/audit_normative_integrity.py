from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path

from app.services.normative_integrity_audit import (
    NormativeIntegrityAuditError,
    run_audit,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.3: audita integridad artículo↔texto y cobertura temporal "
            "del corpus normativo de recuperación."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("deployment/runtime_artifacts_19f/chunks.jsonl"),
        help="JSONL de subchunks del runtime 19F.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/sprint19I3"),
        help="Directorio de reportes. No modifica el corpus ni FAISS.",
    )
    parser.add_argument(
        "--expected-total",
        type=int,
        default=29402,
        help="Cardinalidad esperada; use 0 para desactivar la comprobación.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Devuelve código 2 si hay contradicciones artículo↔texto o fechas "
            "temporales inválidas. Los metadatos temporales desconocidos se "
            "reportan, pero no son por sí solos error de ejecución."
        ),
    )
    return parser.parse_args()


def _summary_int(summary: Mapping[str, object], key: str) -> int:
    value = summary.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise NormativeIntegrityAuditError(
            f"El resumen de auditoría contiene un valor no entero para {key!r}: "
            f"{value!r}."
        )
    return value


def main() -> int:
    args = parse_args()
    try:
        findings, summary, outputs = run_audit(
            input_path=args.input,
            output_dir=args.output_dir,
        )
    except NormativeIntegrityAuditError as exc:
        print(f"ERROR: {exc}")
        return 1

    total_chunks = _summary_int(summary, "total_chunks")
    if args.expected_total and total_chunks != args.expected_total:
        print(
            "ERROR: cardinalidad inesperada: "
            f"esperados={args.expected_total}, encontrados={total_chunks}."
        )
        return 1

    print("OK: Sprint 19I.3; auditoría normativa completada")
    print(f"- chunks_totales={total_chunks}")
    print(f"- chunks_normativos={summary['normative_chunks']}")
    print(f"- documentos_normativos={summary['normative_documents']}")
    print(f"- article_match={summary['article_match']}")
    print(f"- article_mismatch={summary['article_mismatch']}")
    print(f"- text_without_article={summary['text_without_article']}")
    print(f"- metadata_without_article={summary['metadata_without_article']}")
    print(f"- temporal_bounded={summary['temporal_bounded']}")
    print(f"- temporal_open_end={summary['temporal_open_end']}")
    print(f"- temporal_open_start={summary['temporal_open_start']}")
    print(f"- temporal_unknown={summary['temporal_unknown']}")
    print(f"- temporal_invalid={summary['temporal_invalid']}")
    print(f"- promotion_eligible={summary['promotion_eligible']}")
    for label, path in outputs.items():
        print(f"- {label}={path}")

    if args.strict and (
        _summary_int(summary, "article_mismatch") > 0
        or _summary_int(summary, "temporal_invalid") > 0
    ):
        print(
            "STRICT: se detectaron inconsistencias que requieren saneamiento "
            "antes de reconstruir artefactos."
        )
        return 2

    # `findings` se conserva para obligar a materializar/validar el resultado.
    if not findings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
