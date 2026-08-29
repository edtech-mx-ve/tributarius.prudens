from __future__ import annotations

from pathlib import Path

from app.services.publication_staging_audit_19i18s import (
    PublicationStagingAuditError,
    audit_publication_staging,
)


def main() -> int:
    try:
        result = audit_publication_staging(Path("."))
    except PublicationStagingAuditError as exc:
        print(f"ERROR: Sprint 19I.18S; auditoría de staging falló: {exc}")
        return 1

    print("Sprint 19I.18S; auditoría de staging para publicación")
    print(f"- staged_count={result.staged_count}")
    print(f"- forbidden_paths={','.join(result.forbidden_paths) or 'none'}")
    print(
        "- render_sha_matches_public_candidate="
        f"{result.render_sha_matches_public_candidate}"
    )
    print(
        "- temporal_registry_staged_or_tracked="
        f"{result.temporal_registry_staged_or_tracked}"
    )
    print(f"- accepted={result.accepted}")

    if not result.accepted:
        print("DECISION=DO_NOT_COMMIT")
        return 1

    print("DECISION=SAFE_TO_COMMIT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
