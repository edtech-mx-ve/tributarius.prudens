from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.services.runtime_browser_official_batch_import import (
    BatchImportError,
    import_batch,
)

DEFAULT_PLAN = Path("reports/sprint19I18J8/browser_official_download_plan.json")
DEFAULT_EVIDENCE_DIR = Path("dist/browser_official_evidence_19i18j6")
DEFAULT_REPORT = Path("reports/sprint19I18J9/browser_official_batch_import.json")
RESOURCE_DIR = Path("app/resources")
REQUIRED_CAMERA_DOCUMENTS = {
    "cff",
    "cpeum",
    "lfdc",
    "lfisan",
    "lfpca",
    "lieps",
    "lif_2026",
    "lisr",
    "liva",
    "lotfja",
    "reg_cff",
    "reg_lisr_060516",
    "reg_liva_250914",
}


def _load_json_object(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _extract_entries(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = payload.get("documents", payload.get("entries"))
    if isinstance(raw, dict):
        return {
            str(key): value
            for key, value in raw.items()
            if isinstance(value, dict)
        }
    if isinstance(raw, list):
        result: dict[str, dict[str, Any]] = {}
        for item in raw:
            if not isinstance(item, dict):
                continue
            document_id = item.get("document_id")
            if isinstance(document_id, str) and document_id:
                result[document_id] = item
        return result
    return {}


def _candidate_is_trusted_registry(path: Path) -> bool:
    payload = _load_json_object(path)
    if payload is None:
        return False
    entries = _extract_entries(payload)
    if not REQUIRED_CAMERA_DOCUMENTS.issubset(entries):
        return False

    for document_id in REQUIRED_CAMERA_DOCUMENTS:
        entry = entries[document_id]
        urls = entry.get("candidate_urls") or entry.get("source_urls") or []
        if isinstance(urls, str):
            urls = [urls]
        if not isinstance(urls, list) or not urls:
            return False
        if not any(
            isinstance(url, str)
            and url.startswith("https://www.diputados.gob.mx/")
            for url in urls
        ):
            return False
    return True


def discover_registry(resource_dir: Path = RESOURCE_DIR) -> Path:
    if not resource_dir.is_dir():
        raise BatchImportError(
            f"No existe el directorio de recursos: {resource_dir}"
        )

    candidates = sorted(
        path
        for path in resource_dir.glob("*.json")
        if "official" in path.name.lower()
        and "source" in path.name.lower()
        and _candidate_is_trusted_registry(path)
    )

    if not candidates:
        raise BatchImportError(
            "No se encontró un registro oficial compatible en app/resources. "
            "Use --registry para indicar explícitamente el archivo."
        )
    if len(candidates) > 1:
        joined = ", ".join(str(path) for path in candidates)
        raise BatchImportError(
            "Se encontraron varios registros oficiales compatibles; "
            f"use --registry para seleccionar uno: {joined}"
        )
    return candidates[0]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.18J.9: importación atómica del lote "
            "descargado mediante navegador."
        )
    )
    parser.add_argument("--downloads-dir", type=Path, required=True)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    try:
        registry = args.registry or discover_registry()
        manifest = args.evidence_dir / "evidence_manifest.json"
        report = import_batch(
            downloads_dir=args.downloads_dir,
            plan_path=args.plan,
            registry_path=registry,
            evidence_dir=args.evidence_dir,
            manifest_path=manifest,
            report_path=args.report,
        )
    except BatchImportError as exc:
        print(f"ERROR: {exc}")
        return 3

    print("OK: Sprint 19I.18J.9; lote de evidencia oficial procesado")
    print(f"- registry={registry}")
    print(f"- status={report['status']}")
    print(f"- imported_count={report['imported_count']}")
    print(f"- imported_documents={','.join(report['imported_documents'])}")
    print(
        "- skipped_existing_pending_documents="
        f"{','.join(report['skipped_existing_pending_documents'])}"
    )
    print("- public_release_allowed=False")
    print(f"- report={args.report}")
    print("NEXT: python -m scripts.audit_browser_official_evidence_19i18j7")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
