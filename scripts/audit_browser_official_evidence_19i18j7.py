from __future__ import annotations

import argparse
from pathlib import Path

from app.services.runtime_browser_evidence_bridge import (
    audit_browser_evidence_against_local_bridge,
    write_browser_bridge_report,
)
from app.services.runtime_official_source_audit import OfficialSourceAuditError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compara evidencia oficial descargada manualmente desde navegador "
            "contra el PDF local ya verificado por el bridge 19I.18I."
        )
    )
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        default=Path("dist/browser_official_evidence_19i18j6"),
    )
    parser.add_argument(
        "--bridge-report",
        type=Path,
        default=Path("reports/sprint19I18I/runtime_source_bridge.json"),
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path(
            "app/resources/runtime_official_source_candidates_19i18j.json"
        ),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(
            "reports/sprint19I18J7/browser_official_evidence_bridge.json"
        ),
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        summary = audit_browser_evidence_against_local_bridge(
            browser_evidence_dir=args.evidence_dir,
            bridge_report_path=args.bridge_report,
            candidate_registry_path=args.registry,
        )
        write_browser_bridge_report(summary, args.report)
    except OfficialSourceAuditError as exc:
        print(f"ERROR: {exc}")
        return 2

    print("OK: Sprint 19I.18J.7; evidencia navegador -> PDF local auditada")
    print(f"- observed_browser_documents={summary.observed_browser_documents}")
    print(
        "- exact_binary_verified_documents="
        + ",".join(summary.exact_binary_verified_documents)
    )
    print(
        "- differing_binary_documents="
        + ",".join(summary.differing_binary_documents)
    )
    print("- blocked_documents=" + ",".join(summary.blocked_documents))
    for item in summary.documents:
        print(
            f"  {item.document_id}: evidence_sha256="
            f"{item.browser_evidence_sha256}; "
            f"local_sha256={item.local_source_sha256}; "
            f"integrity={item.evidence_integrity_ok}; "
            f"exact_binary_match={item.exact_binary_match}; "
            f"status={item.official_binary_provenance_status}"
        )
    print(f"- public_release_allowed={summary.public_release_allowed}")
    print(f"- report={args.report}")
    print(
        "POLICY: una coincidencia SHA-256 acredita identidad binaria entre "
        "la evidencia descargada manualmente desde la URL oficial registrada "
        "y el PDF local verificado. No concede ni presume derechos de "
        "redistribución y no habilita publicación, GitHub Release ni Render."
    )
    return 0 if not summary.blocked_documents else 3


if __name__ == "__main__":
    raise SystemExit(main())
