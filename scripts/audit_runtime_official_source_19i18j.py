from __future__ import annotations

import argparse
from pathlib import Path

from app.services.runtime_official_source_audit import (
    OfficialSourceAuditError,
    audit_official_source_provenance,
    write_official_source_provenance_report,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compara por SHA-256 cada PDF local enlazado al runtime con "
            "candidatos descargados directamente de autoridades oficiales."
        )
    )
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument(
        "--max-mb",
        type=int,
        default=50,
        help="Tamaño máximo permitido por PDF remoto.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.timeout <= 0 or args.max_mb <= 0:
        print("ERROR: timeout y max-mb deben ser positivos.")
        return 2

    try:
        summary = audit_official_source_provenance(
            bridge_report_path=Path(
                "reports/sprint19I18I/runtime_source_bridge.json"
            ),
            candidate_registry_path=Path(
                "app/resources/runtime_official_source_candidates_19i18j.json"
            ),
            timeout_seconds=args.timeout,
            max_bytes=args.max_mb * 1024 * 1024,
        )
        report = Path(
            "reports/sprint19I18J/runtime_official_source_provenance.json"
        )
        write_official_source_provenance_report(summary, report)
    except OfficialSourceAuditError as exc:
        print(f"ERROR: {exc}")
        return 2

    print("OK: Sprint 19I.18J; procedencia PDF local -> fuente oficial auditada")
    print(f"- candidate_documents={summary.candidate_documents}")
    print(
        f"- bridge_verified_documents={summary.bridge_verified_documents}"
    )
    print(
        "- official_provenance_verified_documents="
        + ",".join(summary.official_provenance_verified_documents)
    )
    print(
        "- official_provenance_blocked_documents="
        + ",".join(summary.official_provenance_blocked_documents)
    )
    print(
        "- promotion_ready_documents="
        + ",".join(summary.promotion_ready_documents)
    )
    print(f"- public_release_allowed={summary.public_release_allowed}")
    for item in summary.documents:
        print(
            f"  {item.document_id}: exact_hash_match={item.exact_hash_match}; "
            f"matching_official_url={item.matching_official_url or ''}; "
            f"remote_hashes={len(item.remote_sha256_values)}; "
            f"fetch_errors={len(item.fetch_errors)}"
        )
    print(f"- report={report}")
    print(
        "POLICY: solo un SHA-256 remoto oficial idéntico al PDF local "
        "verifica procedencia exacta. Una URL válida con hash distinto queda "
        "bloqueada; 19I.18J no promueve todavía la política de publicación."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
