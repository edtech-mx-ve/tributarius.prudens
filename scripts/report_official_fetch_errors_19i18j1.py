from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    report_path = Path(
        "reports/sprint19I18J/runtime_official_source_provenance.json"
    )
    if not report_path.is_file():
        print(f"ERROR: reporte no encontrado: {report_path}")
        return 2

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    documents = payload.get("documents", [])
    print("Sprint 19I.18J.1 - detalle de descargas oficiales")
    for item in documents:
        document_id = item.get("document_id", "<unknown>")
        errors = item.get("fetch_errors", [])
        if errors:
            print(f"- {document_id}")
            for error in errors:
                print(f"  {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
