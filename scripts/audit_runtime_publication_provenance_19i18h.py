from __future__ import annotations

from pathlib import Path

from app.services.runtime_publication_provenance_audit import (
    RuntimePublicationProvenanceError,
    audit_runtime_publication_provenance,
    write_runtime_publication_provenance_report,
)


def main() -> int:
    try:
        summary = audit_runtime_publication_provenance(
            chunks_path=Path(
                "deployment/runtime_artifacts_semantic_v2/chunks.jsonl"
            ),
            policy_path=Path(
                "app/resources/runtime_publication_provenance_policy_19i18h.json"
            ),
        )
        report = Path(
            "reports/sprint19I18H/runtime_publication_provenance.json"
        )
        write_runtime_publication_provenance_report(summary, report)
    except RuntimePublicationProvenanceError as exc:
        print(f"ERROR: {exc}")
        return 2

    print("OK: Sprint 19I.18H; procedencia oficial del runtime auditada")
    print(f"- runtime_chunks={summary.runtime_chunks}")
    print(f"- candidate_documents={summary.candidate_documents}")
    print(
        "- missing_candidate_documents="
        + ",".join(summary.missing_candidate_documents)
    )
    print(
        "- provenance_verified_documents="
        + ",".join(summary.provenance_verified_documents)
    )
    print(
        "- provenance_blocked_documents="
        + ",".join(summary.provenance_blocked_documents)
    )
    print(
        "- promotion_ready_documents="
        + ",".join(summary.promotion_ready_documents)
    )
    print(f"- public_release_allowed={summary.public_release_allowed}")
    for item in summary.documents:
        print(
            f"  {item.document_id}: chunks={item.chunk_count}; "
            f"filenames={len(item.source_filenames)}; "
            f"source_sha256={len(item.source_sha256_values)}; "
            f"source_urls={len(item.source_urls)}; "
            f"missing_source_url_chunks={item.missing_source_url_chunks}; "
            f"provenance_ok={item.exact_source_provenance_verified}"
        )
    print(f"- report={report}")
    print(
        "POLICY: 19I.18H no infiere procedencia desde nombres de archivo ni "
        "promueve documentos. La fuente oficial debe estar registrada de forma "
        "explícita y verificable."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
