from pathlib import Path

from app.services.public_runtime_acceptance_19i18l import AcceptanceError, execute


def main() -> int:
    output = Path(
        "reports/sprint19I18L/public_runtime_legal_provenance_temporal.json"
    )
    try:
        report = execute(
            Path("dist/public_safe_runtime_19i18k"),
            output,
        )
    except AcceptanceError as exc:
        print(f"ERROR: {exc}")
        return 3

    print(
        "OK: Sprint 19I.18L; "
        "aceptación jurídica/procedencia/temporal consolidada"
    )
    keys = (
        "normative_document_count",
        "provenance_complete",
        "temporal_fail_closed_complete",
        "temporal_validity_complete",
        "redistribution_human_review_required",
        "legal_local_acceptance",
        "publication_legal_acceptance",
        "public_release_allowed",
        "git_push_allowed",
        "github_release_allowed",
        "render_deploy_allowed",
    )
    for key in keys:
        print(f"- {key}={report[key]}")

    print(
        "- official_rebuild_chain_documents="
        + ",".join(report["official_rebuild_chain_documents"])
    )
    print(
        "- temporal_evidence_registered_documents="
        + ",".join(report["temporal_evidence_registered_documents"])
    )
    print(
        "- temporal_guarded_documents="
        + ",".join(report["temporal_guarded_documents"])
    )
    print(f"- report={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
