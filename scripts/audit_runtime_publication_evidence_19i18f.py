from __future__ import annotations

from pathlib import Path

from app.services.runtime_publication_evidence_audit import (
    RuntimePublicationEvidenceError,
    audit_publication_evidence,
    write_evidence_audit_report,
)


def main() -> int:
    try:
        summary = audit_publication_evidence(
            policy_path=Path(
                "app/resources/runtime_publication_policy_19i18e.json"
            ),
            evidence_path=Path(
                "app/resources/runtime_publication_evidence_19i18f.json"
            ),
        )
        report = Path(
            "reports/sprint19I18F/runtime_publication_evidence.json"
        )
        write_evidence_audit_report(summary, report)
    except RuntimePublicationEvidenceError as exc:
        print(f"ERROR: {exc}")
        return 2

    print("OK: Sprint 19I.18F; evidencia jurídica de publicación auditada")
    print(f"- policy_documents={summary.policy_documents}")
    print(f"- evidence_documents={summary.evidence_documents}")
    print(f"- statutory_candidates={summary.statutory_candidates}")
    print(f"- separate_license_review={summary.separate_license_review}")
    print(
        "- missing_evidence_documents="
        + ",".join(summary.missing_evidence_documents)
    )
    print(
        "- extra_evidence_documents="
        + ",".join(summary.extra_evidence_documents)
    )
    print(
        "- promotion_ready_documents="
        + ",".join(summary.promotion_ready_documents)
    )
    print(f"- report={report}")
    print(
        "POLICY: 19I.18F no promueve documentos a publicables. "
        "Los 14 candidatos normativos requieren auditoría de conformidad de "
        "contenido; UNAM y PRODECON requieren revisión de licencia separada."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
