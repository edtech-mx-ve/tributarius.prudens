from pathlib import Path

from app.services.public_release_candidate_19i18m import (
    ReleaseCandidateError,
    execute,
)


def main() -> int:
    try:
        report = execute(
            runtime_root=Path("dist/public_safe_runtime_19i18k"),
            acceptance_19l=Path(
                "reports/sprint19I18L/"
                "public_runtime_legal_provenance_temporal.json"
            ),
            output_dir=Path("dist/public_release_candidate_19i18m"),
        )
    except ReleaseCandidateError as exc:
        print(f"ERROR: {exc}")
        return 3

    print("OK: Sprint 19I.18M; candidato público reproducible auditado localmente")
    keys = (
        "candidate_only",
        "runtime_file_count",
        "zip_file_count",
        "zip_size",
        "zip_sha256",
        "sanitized_private_path_values",
        "runtime_integrity_preserved_after_sanitization",
        "blocked_document_identity_absent",
        "secret_scan_passed",
        "absolute_private_path_scan_passed",
        "forbidden_extension_scan_passed",
        "deterministic_zip_verified",
        "technical_release_candidate_acceptance",
        "publication_legal_acceptance",
        "temporal_validity_complete",
        "redistribution_human_review_required",
        "public_release_allowed",
        "git_push_allowed",
        "github_release_allowed",
        "render_deploy_allowed",
    )
    for key in keys:
        print(f"- {key}={report[key]}")
    print(f"- zip_path={report['zip_path']}")
    print(
        "- report=dist\\public_release_candidate_19i18m\\"
        "release_candidate_acceptance.json"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
