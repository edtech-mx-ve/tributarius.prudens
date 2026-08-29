from __future__ import annotations

import argparse
from pathlib import Path

from app.services.selective_semantic_candidate import (
    SelectiveSemanticCandidateError,
    build_selective_semantic_candidate,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.18J.12.3: construye en aislamiento el candidato "
            "semantic-v2 desde el staging oficial aprobado."
        )
    )
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument(
        "--delta-report",
        type=Path,
        default=Path(
            "reports/sprint19I18J12_2/selective_rebuild_delta.json"
        ),
    )
    parser.add_argument(
        "--current-fiscal-manifest",
        type=Path,
        default=Path("knowledge/metadata/fiscal_corpus_15_manifest.json"),
    )
    parser.add_argument(
        "--staged-fiscal-manifest",
        type=Path,
        default=Path(
            "dist/selective_rebuild_19i18j12_1/"
            "knowledge/metadata/fiscal_corpus_15_manifest.json"
        ),
    )
    parser.add_argument(
        "--current-normalized-root",
        type=Path,
        default=Path("knowledge/normalized"),
    )
    parser.add_argument(
        "--staged-normalized-root",
        type=Path,
        default=Path(
            "dist/selective_rebuild_19i18j12_1/knowledge/normalized"
        ),
    )
    parser.add_argument(
        "--current-metadata-root",
        type=Path,
        default=Path("knowledge/metadata"),
    )
    parser.add_argument(
        "--staged-metadata-root",
        type=Path,
        default=Path(
            "dist/selective_rebuild_19i18j12_1/knowledge/metadata"
        ),
    )
    parser.add_argument(
        "--prodecon-manifest",
        type=Path,
        default=Path("knowledge/metadata/prodecon_integration_manifest.json"),
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path("app/resources/fiscal_corpus_15_catalog.json"),
    )
    parser.add_argument(
        "--raw-baseline",
        type=Path,
        default=Path("knowledge/chunks/chunks.jsonl"),
    )
    parser.add_argument(
        "--semantic-baseline",
        type=Path,
        default=Path("knowledge/chunks/chunks_semantic_v2.jsonl"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("dist/selective_semantic_candidate_19i18j12_3"),
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = build_selective_semantic_candidate(
            project_root=args.project_root,
            delta_report_path=args.delta_report,
            current_fiscal_manifest_path=args.current_fiscal_manifest,
            staged_fiscal_manifest_path=args.staged_fiscal_manifest,
            current_normalized_root=args.current_normalized_root,
            staged_normalized_root=args.staged_normalized_root,
            current_metadata_root=args.current_metadata_root,
            staged_metadata_root=args.staged_metadata_root,
            prodecon_manifest_path=args.prodecon_manifest,
            catalog_path=args.catalog,
            raw_baseline_path=args.raw_baseline,
            semantic_baseline_path=args.semantic_baseline,
            output_dir=args.output_dir,
            overwrite=args.overwrite,
        )
    except SelectiveSemanticCandidateError as exc:
        print(f"ERROR: {exc}")
        return 3

    print("OK: Sprint 19I.18J.12.3; candidato semántico aislado construido")
    print(
        "- semantic_changed_documents="
        + ",".join(report["semantic_changed_documents"])
    )
    print(
        "- unauthorized_semantic_changed_documents="
        + ",".join(report["unauthorized_semantic_changed_documents"])
    )
    print(f"- candidate_parent_count={report['candidate_parent_count']}")
    print(f"- candidate_sha256={report['candidate_sha256']}")
    print(
        "- candidate_ready_for_transactional_promotion="
        f"{report['candidate_ready_for_transactional_promotion']}"
    )
    print("- canonical_mutation_performed=False")
    print("- runtime_index_mutated=False")
    print("- public_release_allowed=False")
    print(f"- output_dir={args.output_dir}")
    return (
        0
        if report["candidate_ready_for_transactional_promotion"]
        else 3
    )


if __name__ == "__main__":
    raise SystemExit(main())
