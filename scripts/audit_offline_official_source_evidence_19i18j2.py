from __future__ import annotations

import argparse
from pathlib import Path

from app.services.runtime_official_source_audit import OfficialSourceAuditError
from app.services.runtime_official_source_offline_evidence import (
    audit_offline_official_evidence,
    write_offline_evidence_audit_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audita offline un bundle de PDFs adquirido desde fuentes oficiales "
            "en otra máquina/red y lo compara contra el bridge 19I.18I."
        )
    )
    parser.add_argument(
        "--evidence-dir",
        default="dist/official_source_evidence_19i18j2",
    )
    args = parser.parse_args()

    try:
        summary = audit_offline_official_evidence(
            bridge_report_path=Path(
                "reports/sprint19I18I/runtime_source_bridge.json"
            ),
            candidate_registry_path=Path(
                "app/resources/runtime_official_source_candidates_19i18j.json"
            ),
            evidence_bundle_dir=Path(args.evidence_dir),
        )
        report = Path(
            "reports/sprint19I18J2/offline_official_source_evidence.json"
        )
        write_offline_evidence_audit_report(summary, report)
    except OfficialSourceAuditError as exc:
        print(f"ERROR: {exc}")
        return 2

    print("OK: Sprint 19I.18J.2; evidencia oficial offline auditada")
    print(f"- candidate_documents={summary.candidate_documents}")
    print(f"- evidence_records={summary.evidence_records}")
    print("- verified_documents=" + ",".join(summary.verified_documents))
    print("- blocked_documents=" + ",".join(summary.blocked_documents))
    print(
        "- missing_evidence_documents="
        + ",".join(summary.missing_evidence_documents)
    )
    print(
        "- promotion_ready_documents="
        + ",".join(summary.promotion_ready_documents)
    )
    print(f"- public_release_allowed={summary.public_release_allowed}")
    for item in summary.documents:
        print(
            f"  {item.document_id}: integrity={item.evidence_integrity_ok}; "
            f"exact_local_hash_match={item.exact_local_hash_match}; "
            f"blocked_reason={item.blocked_reason or ''}"
        )
    print(f"- report={report}")
    print(
        "POLICY: el bundle offline solo verifica procedencia binaria exacta. "
        "No habilita redistribución ni publicación por sí mismo."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
