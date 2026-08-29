from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.services.public_release_deployment_dependency_19i18o import (
    DeploymentDependencyError,
    execute,
)

DEFAULT_CANDIDATE = Path(
    "dist/public_release_candidate_19i18m/"
    "tributarius-prudens-public-runtime-candidate.zip"
)
DEFAULT_REPORT_19N = Path(
    "dist/public_release_cold_start_19i18n/cold_start_acceptance.json"
)
DEFAULT_OUTPUT = Path("dist/public_release_deployment_dependency_19i18o")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.18O: cierre local de dependencia externa "
            "del modelo de embeddings."
        )
    )
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--report-19n", type=Path, default=DEFAULT_REPORT_19N)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        report = execute(
            candidate_zip=args.candidate,
            report_19n=args.report_19n,
            output_dir=args.output,
        )
    except DeploymentDependencyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(
        "OK: Sprint 19I.18O; dependencia de embeddings "
        "cerrada localmente"
    )
    ordered = [
        "candidate_zip_sha256",
        "canonical_sha256",
        "model_id",
        "fresh_unauthenticated_model_fetch_passed",
        "isolated_model_cache_created",
        "isolated_model_cache_bytes",
        "offline_model_reload_passed",
        "semantic_query_embedding_cold_start_proven",
        "embedding_dimension",
        "faiss_dimension",
        "faiss_ntotal",
        "runtime_loaded_from_candidate_only",
        "source_corpus_not_used",
        "commercial_api_required",
        "api_key_required",
        "credit_card_required",
        "deployment_sufficiency_acceptance",
        "model_weights_in_public_candidate",
        "model_cache_local_build_artifact_only",
        "model_license_review_required",
        "publication_legal_acceptance",
        "temporal_validity_complete",
        "redistribution_human_review_required",
        "public_release_allowed",
        "git_push_allowed",
        "github_release_allowed",
        "render_deploy_allowed",
    ]
    for key in ordered:
        print(f"- {key}={report[key]}")
    print(
        "- report="
        f"{args.output / 'deployment_dependency_acceptance.json'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
