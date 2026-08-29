from __future__ import annotations

from pathlib import Path

from app.services.runtime_browser_official_download_plan import (
    build_browser_download_plan,
    write_browser_download_plan,
)
from app.services.runtime_official_source_audit import OfficialSourceAuditError


def main() -> int:
    try:
        summary = build_browser_download_plan(
            candidate_registry_path=Path(
                "app/resources/runtime_official_source_candidates_19i18j.json"
            ),
            authority_host="www.diputados.gob.mx",
            browser_manifest_path=Path(
                "dist/browser_official_evidence_19i18j6/evidence_manifest.json"
            ),
            browser_bridge_report_path=Path(
                "reports/sprint19I18J7/browser_official_evidence_bridge.json"
            ),
        )
        report = Path(
            "reports/sprint19I18J8/browser_official_download_plan.json"
        )
        write_browser_download_plan(summary, report)
    except OfficialSourceAuditError as exc:
        print(f"ERROR: {exc}")
        return 2

    print("OK: Sprint 19I.18J.8; plan de descarga oficial por navegador")
    print(f"- authority_host={summary.authority_host}")
    print(f"- candidate_documents={summary.candidate_documents}")
    print(
        "- exact_binary_verified_documents="
        + ",".join(summary.exact_binary_verified_documents)
    )
    print(
        "- imported_unverified_documents="
        + ",".join(summary.imported_unverified_documents)
    )
    print(
        "- pending_download_documents="
        + ",".join(summary.pending_download_documents)
    )
    print()
    print("PLAN:")
    for item in summary.items:
        print(f"[{item.status}] {item.document_id}")
        print(f"  URL: {item.source_url}")
        print(f"  Guardar como: {item.expected_filename}")
        if item.status != "exact_binary_verified":
            print("  Importar:")
            for line in item.import_command.splitlines():
                print(f"    {line}")
    print(f"- report={report}")
    print(
        "POLICY: use únicamente la URL oficial impresa por este plan. "
        "Descargue con el botón de descarga del visor, no mediante imprimir/"
        "guardar como PDF. Este plan no cambia derechos de redistribución, "
        "vigencia temporal ni autorización de publicación."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
