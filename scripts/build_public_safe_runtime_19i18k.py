from __future__ import annotations

import argparse
from pathlib import Path

from app.services.public_safe_runtime_19i18k import (
    PublicSafeRuntimeError,
    execute_public_safe_runtime,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.18K: construye localmente un runtime publicable "
            "normative-only, excluyendo UNAM/PRODECON y manteniendo publicación bloqueada."
        )
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
        "--output-dir",
        type=Path,
        default=Path("dist/public_safe_runtime_19i18k"),
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
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--allow-model-download", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = execute_public_safe_runtime(
            canonical_path=args.canonical,
            canonical_manifest_path=args.canonical_manifest,
            output_dir=args.output_dir,
            cases_path=args.cases,
            policy_path=args.policy,
            batch_size=args.batch_size,
            local_files_only=not args.allow_model_download,
        )
    except PublicSafeRuntimeError as exc:
        print(f"ERROR: {exc}")
        return 3

    print("OK: Sprint 19I.18K; runtime público seguro construido localmente")
    print("- scope=normative_only")
    print(f"- normative_document_count={report['normative_document_count']}")
    print("- excluded_documents=" + ",".join(report["excluded_documents"]))
    print(f"- parent_count={report['parent_count']}")
    print(f"- canonical_sha256={report['canonical_sha256']}")
    print(f"- normative_eval_case_count={report['normative_eval_case_count']}")
    for key, value in report["metrics"].items():
        print(f"- {key}={value:.3f}")
    print(f"- benchmark_passed={report['benchmark_passed']}")
    print("- blocked_content_absent=True")
    print(
        "- legal_basis_status="
        f"{report['legal_basis_status']}"
    )
    print("- redistribution_human_review_required=True")
    print("- temporal_validity_complete=False")
    print("- technical_local_acceptance=True")
    print("- public_release_allowed=False")
    print("- git_push_allowed=False")
    print("- github_release_allowed=False")
    print("- render_deploy_allowed=False")
    print(f"- report={args.output_dir / 'public_safe_runtime_acceptance.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
