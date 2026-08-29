from __future__ import annotations

from pathlib import Path

from app.services.runtime_official_source_audit import OfficialSourceAuditError
from app.services.runtime_publication_decision_matrix import (
    build_publication_decision_matrix,
    write_publication_decision_matrix,
)


def main() -> int:
    try:
        summary = build_publication_decision_matrix(
            safety_report_path=Path(
                "reports/sprint19I18E/runtime_publication_safety.json"
            ),
            evidence_registry_path=Path(
                "app/resources/runtime_publication_evidence_19i18f.json"
            ),
            content_report_path=Path(
                "reports/sprint19I18G/runtime_publication_content_conformity.json"
            ),
            source_bridge_report_path=Path(
                "reports/sprint19I18I/runtime_source_bridge.json"
            ),
            official_source_report_path=Path(
                "reports/sprint19I18J/runtime_official_source_provenance.json"
            ),
        )
        report = Path(
            "reports/sprint19I18J3/runtime_publication_decision_matrix.json"
        )
        write_publication_decision_matrix(summary, report)
    except OfficialSourceAuditError as exc:
        print(f"ERROR: {exc}")
        return 2

    print("OK: Sprint 19I.18J.3; matriz de decisión de publicación generada")
    print(f"- observed_documents={summary.observed_documents}")
    print(
        "- publication_ready_documents="
        + ",".join(summary.publication_ready_documents)
    )
    print("- blocked_documents=" + ",".join(summary.blocked_documents))
    print(
        "- unresolved_external_evidence_documents="
        + ",".join(summary.unresolved_external_evidence_documents)
    )
    print(
        "- separate_license_review_documents="
        + ",".join(summary.separate_license_review_documents)
    )
    print(f"- public_release_allowed={summary.public_release_allowed}")
    for item in summary.documents:
        print(
            f"  {item.document_id}: official={item.official_source_status}; "
            f"policy={item.publication_policy_status}; "
            f"ready={item.publication_ready}; "
            f"blockers={','.join(item.blockers)}"
        )
    print(f"- report={report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
