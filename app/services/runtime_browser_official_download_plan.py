from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

from app.services.runtime_official_source_audit import OfficialSourceAuditError


@dataclass(frozen=True)
class BrowserDownloadPlanItem:
    document_id: str
    source_url: str
    expected_filename: str
    status: str
    import_command: str


@dataclass(frozen=True)
class BrowserDownloadPlanSummary:
    authority_host: str
    candidate_documents: int
    exact_binary_verified_documents: tuple[str, ...]
    imported_unverified_documents: tuple[str, ...]
    pending_download_documents: tuple[str, ...]
    items: tuple[BrowserDownloadPlanItem, ...]


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OfficialSourceAuditError(f"No se pudo leer JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise OfficialSourceAuditError(f"{path} debe contener un objeto JSON.")
    return payload


def _browser_manifest_ids(path: Path | None) -> set[str]:
    if path is None or not path.exists():
        return set()
    payload = _read_json(path)
    raw = payload.get("documents")
    if not isinstance(raw, list):
        raise OfficialSourceAuditError("Manifest navegador sin documents.")
    result: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise OfficialSourceAuditError("Entrada manifest navegador inválida.")
        document_id = item.get("document_id")
        if not isinstance(document_id, str) or not document_id:
            raise OfficialSourceAuditError("document_id inválido en manifest navegador.")
        if document_id in result:
            raise OfficialSourceAuditError(
                f"document_id duplicado en manifest navegador: {document_id}"
            )
        result.add(document_id)
    return result


def _verified_ids(path: Path | None) -> set[str]:
    if path is None or not path.exists():
        return set()
    payload = _read_json(path)
    raw = payload.get("exact_binary_verified_documents")
    if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
        raise OfficialSourceAuditError(
            "Reporte J.7 sin exact_binary_verified_documents válido."
        )
    return set(raw)


def build_browser_download_plan(
    *,
    candidate_registry_path: Path,
    authority_host: str,
    browser_manifest_path: Path | None = None,
    browser_bridge_report_path: Path | None = None,
    download_dir_expression: str = "$env:USERPROFILE\\Downloads",
) -> BrowserDownloadPlanSummary:
    registry = _read_json(candidate_registry_path)
    raw_docs = registry.get("documents")
    if not isinstance(raw_docs, list):
        raise OfficialSourceAuditError("Registry oficial sin documents.")

    imported = _browser_manifest_ids(browser_manifest_path)
    verified = _verified_ids(browser_bridge_report_path)

    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw in raw_docs:
        if not isinstance(raw, dict):
            raise OfficialSourceAuditError("Entrada registry inválida.")
        document_id = raw.get("document_id")
        urls = raw.get("candidate_urls")
        if (
            not isinstance(document_id, str)
            or not document_id
            or not isinstance(urls, list)
            or not urls
            or not all(isinstance(url, str) and url for url in urls)
        ):
            raise OfficialSourceAuditError("Registry oficial inválido.")
        if document_id in seen:
            raise OfficialSourceAuditError(
                f"document_id duplicado en registry: {document_id}"
            )
        seen.add(document_id)

        selected_url = None
        for url in urls:
            parsed = urlparse(url)
            if (
                parsed.scheme.lower() == "https"
                and (parsed.hostname or "").lower() == authority_host.lower()
            ):
                selected_url = url
                break
        if selected_url is not None:
            candidates.append((document_id, selected_url))

    candidate_ids = {document_id for document_id, _ in candidates}
    if not verified.issubset(candidate_ids):
        unexpected = ",".join(sorted(verified - candidate_ids))
        raise OfficialSourceAuditError(
            f"J.7 contiene documentos fuera de {authority_host}: {unexpected}"
        )
    if not imported.issubset(candidate_ids):
        unexpected = ",".join(sorted(imported - candidate_ids))
        raise OfficialSourceAuditError(
            f"Manifest navegador contiene documentos fuera de {authority_host}: "
            f"{unexpected}"
        )

    items: list[BrowserDownloadPlanItem] = []
    pending: list[str] = []
    imported_unverified: list[str] = []

    for document_id, source_url in sorted(candidates):
        filename = f"{document_id}.pdf"
        if document_id in verified:
            status = "exact_binary_verified"
        elif document_id in imported:
            status = "imported_pending_bridge_audit"
            imported_unverified.append(document_id)
        else:
            status = "pending_browser_download"
            pending.append(document_id)

        input_expression = f'{download_dir_expression}\\{filename}'
        command = (
            "python -m scripts.import_browser_official_evidence_19i18j6 "
            f"`\n  --document-id {document_id} `\n"
            f'  --input-pdf "{input_expression}"'
        )
        items.append(
            BrowserDownloadPlanItem(
                document_id=document_id,
                source_url=source_url,
                expected_filename=filename,
                status=status,
                import_command=command,
            )
        )

    return BrowserDownloadPlanSummary(
        authority_host=authority_host.lower(),
        candidate_documents=len(items),
        exact_binary_verified_documents=tuple(sorted(verified)),
        imported_unverified_documents=tuple(sorted(imported_unverified)),
        pending_download_documents=tuple(sorted(pending)),
        items=tuple(items),
    )


def write_browser_download_plan(
    summary: BrowserDownloadPlanSummary,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(asdict(summary), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
