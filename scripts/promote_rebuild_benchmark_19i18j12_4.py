from __future__ import annotations

import argparse
from pathlib import Path

from app.services.transactional_rag_promotion import (
    EXPECTED_CANDIDATE_SHA256,
    TransactionalRagPromotionError,
    execute_transactional_rag_promotion,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.18J.12.4: reconstruye RAG en staging, ejecuta benchmark "
            "y solo entonces promueve canonical+runtime con snapshot/rollback."
        )
    )
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument(
        "--candidate-dir",
        type=Path,
        default=Path("dist/selective_semantic_candidate_19i18j12_3"),
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path("dist/transactional_rag_19i18j12_4"),
    )
    parser.add_argument(
        "--snapshot-root",
        type=Path,
        default=Path("dist/snapshots_19i18j12_4"),
    )
    parser.add_argument(
        "--canonical",
        type=Path,
        default=Path("knowledge/chunks/chunks_semantic_v2.jsonl"),
    )
    parser.add_argument(
        "--canonical-manifest",
        type=Path,
        default=Path("knowledge/chunks/chunks_semantic_v2_manifest.json"),
    )
    parser.add_argument(
        "--retrieval-target",
        type=Path,
        default=Path("knowledge/retrieval_chunks_semantic_v2"),
    )
    parser.add_argument(
        "--runtime-target",
        type=Path,
        default=Path("deployment/runtime_artifacts_semantic_v2"),
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("app/resources/retrieval_eval_cases.json"),
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path("app/resources/legal_retrieval_policy.json"),
    )
    parser.add_argument(
        "--expected-candidate-sha256",
        default=EXPECTED_CANDIDATE_SHA256,
    )
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument(
        "--allow-model-download",
        action="store_true",
        help="Desactiva local-files-only. No usar si el modelo ya está cacheado.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = execute_transactional_rag_promotion(
            project_root=args.project_root,
            candidate_dir=args.candidate_dir,
            work_dir=args.work_dir,
            snapshot_root=args.snapshot_root,
            canonical_path=args.canonical,
            canonical_manifest_path=args.canonical_manifest,
            retrieval_target=args.retrieval_target,
            runtime_target=args.runtime_target,
            cases_path=args.cases,
            policy_path=args.policy,
            expected_sha256=args.expected_candidate_sha256,
            local_files_only=not args.allow_model_download,
            batch_size=args.batch_size,
        )
    except TransactionalRagPromotionError as exc:
        print(f"ERROR: {exc}")
        return 3

    print("OK: Sprint 19I.18J.12.4; promoción RAG transaccional completada")
    print(f"- canonical_sha256={report['canonical_sha256']}")
    print(f"- parent_count={report['parent_count']}")
    for key, value in report["metrics"].items():
        print(f"- {key}={value:.3f}")
    print("- benchmark_passed=True")
    print("- rollback_snapshot_created=True")
    print("- canonical_mutation_performed=True")
    print("- runtime_mutation_performed=True")
    print("- public_release_allowed=False")
    print(f"- snapshot_dir={report['snapshot_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
