from __future__ import annotations

import argparse
from pathlib import Path

from app.services.semantic_corpus_promotion import (
    SemanticCorpusPromotionError,
    promote_semantic_corpus,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.7.12: aplica el gate integral y promueve el candidato "
            "semántico a un artefacto canónico versionado."
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
        "--promoted",
        type=Path,
        default=Path("knowledge/chunks/chunks_semantic_v2.jsonl"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(
            "knowledge/chunks/chunks_semantic_v2_manifest.json"
        ),
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = promote_semantic_corpus(
            baseline_path=args.baseline,
            candidate_path=args.candidate,
            normalized_root=args.normalized_root,
            catalog_path=args.catalog,
            promoted_path=args.promoted,
            manifest_path=args.manifest,
            overwrite=args.overwrite,
        )
    except SemanticCorpusPromotionError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("OK: Sprint 19I.7.12; candidato semántico promovido")
    print(f"- status={result.status}")
    print(f"- baseline_chunks={result.baseline_chunks}")
    print(f"- promoted_chunks={result.promoted_chunks}")
    print(f"- document_count={result.document_count}")
    print(f"- promoted_sha256={result.promoted_sha256}")
    print(f"- promoted={result.promoted_path}")
    print(f"- manifest={args.manifest}")
    print("- gate:")
    print(
        "  legitimate_boundaries_missing="
        f"{result.gate.legitimate_boundaries_missing}"
    )
    print(
        "  duplicate_boundaries_unresolved="
        f"{result.gate.duplicate_boundaries_unresolved}"
    )
    print(
        "  residual_chain="
        f"{result.gate.source_residuals_safe}+"
        f"{result.gate.profile_cases_safe}="
        f"{result.gate.semantic_residuals_review}"
    )
    print(f"  profile_cases_review={result.gate.profile_cases_review}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
