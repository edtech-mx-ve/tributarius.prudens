from __future__ import annotations

import argparse
from pathlib import Path

from app.services.runtime_browser_official_evidence import (
    import_browser_downloaded_official_pdf,
)
from app.services.runtime_official_source_audit import OfficialSourceAuditError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Importa un PDF descargado manualmente desde la URL oficial "
            "mediante navegador y genera evidencia local con SHA-256."
        )
    )
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--input-pdf", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("dist/browser_official_evidence_19i18j6"),
    )
    parser.add_argument("--max-mb", type=int, default=50)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        summary = import_browser_downloaded_official_pdf(
            document_id=args.document_id,
            input_pdf=args.input_pdf,
            output_dir=args.output_dir,
            registry_path=Path(
                "app/resources/runtime_official_source_candidates_19i18j.json"
            ),
            max_bytes=args.max_mb * 1024 * 1024,
        )
    except OfficialSourceAuditError as exc:
        print(f"ERROR: {exc}")
        return 2

    item = summary.items[0]
    print("OK: Sprint 19I.18J.6; PDF oficial importado desde navegador")
    print(f"- document_id={item.document_id}")
    print(f"- source_url={item.source_url}")
    print(f"- sha256={item.sha256}")
    print(f"- size_bytes={item.size_bytes}")
    print(f"- evidence_file={item.evidence_file}")
    print(f"- manifest={summary.manifest_path}")
    print(
        "POLICY: la importación acredita integridad del archivo descargado; "
        "la coincidencia con el PDF local debe verificarse por separado."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
