from __future__ import annotations

import argparse
from pathlib import Path

from app.services.corpus_chunking_service import CorpusChunkingError, build_legal_chunks
from app.services.semantic_canonical_audit import (
    SemanticCanonicalAuditError,
    compare_canonical_corpora,
    write_semantic_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.7: regenera un candidato canónico desde Markdown normalizado "
            "con límites legales semánticamente estrictos y lo compara con 19C."
        )
    )
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path("knowledge/chunks/chunks.jsonl"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/sprint19I7"),
    )
    parser.add_argument("--overwrite-candidate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    candidate = output_dir / "candidate_chunks.jsonl"
    manifest = output_dir / "candidate_chunking_manifest.json"
    report_path = output_dir / "semantic_canonical_report.json"

    if (
        (candidate.exists() or manifest.exists() or report_path.exists())
        and not args.overwrite_candidate
    ):
        print(
            "ERROR: ya existen salidas 19I.7; use --overwrite-candidate "
            "solo para regenerar deliberadamente el candidato."
        )
        return 1

    try:
        build_legal_chunks(
            project_root=args.project_root,
            catalog_path=Path("app/resources/fiscal_corpus_15_catalog.json"),
            fiscal_manifest_path=Path(
                "knowledge/metadata/fiscal_corpus_15_manifest.json"
            ),
            prodecon_manifest_path=Path(
                "knowledge/metadata/prodecon_integration_manifest.json"
            ),
            chunks_path=candidate,
            manifest_path=manifest,
            overwrite=args.overwrite_candidate,
        )
        report = compare_canonical_corpora(
            baseline_path=args.baseline,
            candidate_path=candidate,
        )
        write_semantic_report(report_path, report)
    except (CorpusChunkingError, SemanticCanonicalAuditError) as exc:
        print(f"ERROR: {exc}")
        return 1

    print("OK: Sprint 19I.7; candidato semántico generado sin promoverlo")
    print(f"- baseline_chunks={report.baseline_chunks}")
    print(f"- candidate_chunks={report.candidate_chunks}")
    print(f"- duplicate_candidate_ids={report.duplicate_candidate_ids}")
    print(f"- candidate_empty_text={report.candidate_empty_text}")
    print(f"- candidate={candidate}")
    print(f"- report={report_path}")
    print("- deltas_por_documento:")
    for item in report.documents:
        if (
            item.delta
            or item.labels_only_baseline
            or item.labels_only_candidate
        ):
            print(
                f"  {item.canonical_id}: "
                f"{item.baseline_chunks}->{item.candidate_chunks} "
                f"(delta={item.delta}); "
                f"solo_baseline={len(item.labels_only_baseline)}; "
                f"solo_candidate={len(item.labels_only_candidate)}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
