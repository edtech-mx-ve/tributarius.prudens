from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.services.public_release_cold_start_19i18n import (
    ColdStartError,
    execute,
)

DEFAULT_CANDIDATE = Path(
    "dist/public_release_candidate_19i18m/"
    "tributarius-prudens-public-runtime-candidate.zip"
)
DEFAULT_OUTPUT = Path("dist/public_release_cold_start_19i18n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.18N: cold-start aislado del candidato público 19M."
        )
    )
    parser.add_argument(
        "--candidate",
        type=Path,
        default=DEFAULT_CANDIDATE,
        help="ZIP candidato construido por 19M.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Directorio de salida; no se sobrescribe.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        report = execute(
            candidate_zip=args.candidate,
            output_dir=args.output,
        )
    except ColdStartError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print("OK: Sprint 19I.18N; cold-start aislado validado localmente")
    ordered = [
        "candidate_zip_sha256",
        "candidate_zip_member_count",
        "canonical_sha256",
        "parent_count",
        "chunk_count",
        "unique_document_count",
        "faiss_ntotal",
        "faiss_dimension",
        "manifest_integrity_passed",
        "zip_path_safety_passed",
        "runtime_loaded_from_extracted_candidate_only",
        "source_runtime_path_not_used",
        "blocked_document_identity_absent",
        "cold_start_acceptance",
        "embedding_model_bundled",
        "embedding_model_external_dependency",
        "semantic_query_embedding_cold_start_proven",
        "deployment_sufficiency_acceptance",
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
    print(f"- report={args.output / 'cold_start_acceptance.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
