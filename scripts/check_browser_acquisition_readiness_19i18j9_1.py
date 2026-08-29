from __future__ import annotations

import argparse
from pathlib import Path

from app.services.runtime_browser_acquisition_readiness import (
    AcquisitionReadinessError,
    build_acquisition_readiness,
)

DEFAULT_PLAN = Path("reports/sprint19I18J8/browser_official_download_plan.json")
DEFAULT_MANIFEST = Path(
    "dist/browser_official_evidence_19i18j6/evidence_manifest.json"
)
DEFAULT_REPORT = Path(
    "reports/sprint19I18J9_1/browser_acquisition_readiness.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.18J.9.1: verifica qué PDFs oficiales descargados "
            "están listos para la importación por lote."
        )
    )
    parser.add_argument("--downloads-dir", type=Path, required=True)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    try:
        report = build_acquisition_readiness(
            downloads_dir=args.downloads_dir,
            plan_path=args.plan,
            evidence_manifest_path=args.manifest,
            report_path=args.report,
        )
    except AcquisitionReadinessError as exc:
        print(f"ERROR: {exc}")
        return 3

    print("OK: Sprint 19I.18J.9.1; estado de adquisición evaluado")
    print(
        "- already_available_documents="
        f"{','.join(report['already_available_documents'])}"
    )
    print(
        "- ready_for_batch_import_documents="
        f"{','.join(report['ready_for_batch_import_documents'])}"
    )
    print(
        "- pending_or_invalid_documents="
        f"{','.join(report['pending_or_invalid_documents'])}"
    )
    print(f"- batch_import_allowed={report['batch_import_allowed']}")
    print("- public_release_allowed=False")
    print(f"- report={args.report}")

    for item in report["items"]:
        if item["state"] == "missing_download":
            print(f"[missing] {item['document_id']}")
            print(f"  URL: {item['source_url']}")
            print(f"  Guardar como: {item['expected_filename']}")
        elif item["state"] == "invalid_download":
            print(f"[invalid] {item['document_id']}: {item['detail']}")

    return 0 if report["batch_import_allowed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
