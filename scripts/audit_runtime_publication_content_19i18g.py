from __future__ import annotations

from pathlib import Path

from app.services.runtime_publication_content_audit import (
    RuntimePublicationContentAuditError,
    audit_runtime_publication_content,
    write_runtime_publication_content_report,
)


def main() -> int:
    try:
        summary = audit_runtime_publication_content(
            chunks_path=Path(
                "deployment/runtime_artifacts_semantic_v2/chunks.jsonl"
            ),
            content_policy_path=Path(
                "app/resources/runtime_publication_content_policy_19i18g.json"
            ),
        )
        report = Path(
            "reports/sprint19I18G/runtime_publication_content_conformity.json"
        )
        write_runtime_publication_content_report(summary, report)
    except RuntimePublicationContentAuditError as exc:
        print(f"ERROR: {exc}")
        return 2

    print("OK: Sprint 19I.18G; conformidad técnica del contenido auditada")
    print(f"- runtime_chunks={summary.runtime_chunks}")
    print(f"- candidate_chunks={summary.candidate_chunks}")
    print(f"- candidate_documents={summary.candidate_documents}")
    print(
        "- missing_candidate_documents="
        + ",".join(summary.missing_candidate_documents)
    )
    print(
        "- metadata_nonconformant_documents="
        + ",".join(summary.metadata_nonconformant_documents)
    )
    print(
        "- integrity_nonconformant_documents="
        + ",".join(summary.integrity_nonconformant_documents)
    )
    print(
        "- manual_review_documents="
        + ",".join(summary.manual_review_documents)
    )
    print(
        "- technically_conformant_documents="
        + ",".join(summary.technically_conformant_documents)
    )
    print(
        f"- publication_promotion_allowed={summary.publication_promotion_allowed}"
    )
    for item in summary.documents:
        print(
            f"  {item.document_id}: chunks={item.chunk_count}; "
            f"source_sha256_count={item.source_sha256_count}; "
            f"hash_checked={item.text_hash_checked}; "
            f"hash_mismatch={item.text_hash_mismatch}; "
            f"editorial_marker_hits={item.editorial_marker_hits}; "
            f"metadata_ok={item.metadata_conformant}; "
            f"technical_pass={item.technical_conformity_passed}"
        )
    print(f"- report={report}")
    print(
        "POLICY: este sprint no promueve derechos de redistribución. "
        "Solo identifica conformidad técnica y señales que requieren revisión."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
