from __future__ import annotations

import argparse
from pathlib import Path

from app.services.runtime_official_source_audit import OfficialSourceAuditError
from app.services.runtime_official_source_offline_evidence import (
    acquire_official_evidence_bundle,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Adquiere PDFs desde autoridades oficiales en una máquina/red "
            "con conectividad y genera un bundle transferible con hashes."
        )
    )
    parser.add_argument(
        "--output-dir",
        default="dist/official_source_evidence_19i18j2",
    )
    parser.add_argument(
        "--document-id",
        action="append",
        dest="document_ids",
        default=[],
    )
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--max-mb", type=int, default=50)
    args = parser.parse_args()

    if args.timeout <= 0 or args.max_mb <= 0:
        print("ERROR: timeout y max-mb deben ser positivos.")
        return 2

    try:
        manifest = acquire_official_evidence_bundle(
            candidate_registry_path=Path(
                "app/resources/runtime_official_source_candidates_19i18j.json"
            ),
            output_dir=Path(args.output_dir),
            timeout_seconds=args.timeout,
            max_bytes=args.max_mb * 1024 * 1024,
            document_ids=args.document_ids,
        )
    except OfficialSourceAuditError as exc:
        print(f"ERROR: {exc}")
        return 2

    print("OK: evidencia oficial adquirida")
    print(f"- manifest={manifest}")
    print(
        "POLICY: transfiera la carpeta completa sin modificarla; "
        "la auditoría offline revalidará hashes y autoridad."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
