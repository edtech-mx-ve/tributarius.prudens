from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

AUTHORIZED = {"lfdc", "reg_liva_250914"}


class SelectiveRebuildDeltaError(RuntimeError):
    """Controlled error for J.12.2 delta verification."""


@dataclass(frozen=True)
class DocumentDelta:
    document_id: str
    current_source_sha256: str
    staged_source_sha256: str
    source_changed: bool
    current_normalized_sha256: str
    staged_normalized_sha256: str
    normalized_changed: bool


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SelectiveRebuildDeltaError(f"JSON inválido: {path}") from exc
    if not isinstance(value, dict):
        raise SelectiveRebuildDeltaError(f"Objeto JSON esperado: {path}")
    return value


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _manifest_rows(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("documents")
    if not isinstance(rows, list):
        raise SelectiveRebuildDeltaError("Manifest sin lista documents")
    result: dict[str, dict[str, Any]] = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        document_id = item.get("canonical_id")
        if isinstance(document_id, str):
            result[document_id] = item
    return result


def _required(row: dict[str, Any], key: str, document_id: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise SelectiveRebuildDeltaError(f"{document_id}: falta campo {key}")
    return value


def _manifest_path_candidates(root: Path, row: dict[str, Any]) -> list[Path]:
    candidates: list[Path] = []
    for key in (
        "normalized_path",
        "normalized_markdown_path",
        "markdown_path",
        "output_path",
    ):
        raw = row.get(key)
        if not isinstance(raw, str) or not raw:
            continue
        path = Path(raw)
        if path.is_absolute() and path.is_file():
            candidates.append(path)
            continue
        for candidate in (root / path, root.parent / path):
            if candidate.is_file():
                candidates.append(candidate)
    return candidates


def _normalized_files(root: Path) -> list[Path]:
    if not root.is_dir():
        raise SelectiveRebuildDeltaError(f"Normalized root ausente: {root}")
    return sorted(path for path in root.rglob("*.md") if path.is_file())


def _unique(paths: list[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            result.append(path)
    return result


def _key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return re.sub(r"[^a-z0-9]+", "_", ascii_text.casefold()).strip("_")


def _exact_key_matches(files: list[Path], values: set[str]) -> list[Path]:
    keys = {_key(value) for value in values if value}
    return [path for path in files if _key(path.stem) in keys]


def _find_normalized_for_document(
    root: Path,
    document_id: str,
    row: dict[str, Any],
) -> Path:
    explicit = _unique(_manifest_path_candidates(root, row))
    if len(explicit) == 1:
        return explicit[0]
    if len(explicit) > 1:
        raise SelectiveRebuildDeltaError(
            f"{document_id}: múltiples rutas explícitas de Markdown"
        )

    files = _normalized_files(root)
    identity_values = {document_id}
    for field in ("filename", "title", "name", "display_name"):
        raw = row.get(field)
        if isinstance(raw, str) and raw:
            identity_values.add(Path(raw).stem if field == "filename" else raw)

    matches = _unique(_exact_key_matches(files, identity_values))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise SelectiveRebuildDeltaError(
            f"{document_id}: identidad normalizada ambigua; "
            f"candidatos={len(matches)}"
        )
    raise SelectiveRebuildDeltaError(
        f"{document_id}: Markdown normalizado no resoluble de forma exacta"
    )


def verify_selective_delta(
    *,
    current_manifest_path: Path,
    staged_manifest_path: Path,
    current_normalized_root: Path,
    staged_normalized_root: Path,
    output_path: Path,
) -> dict[str, Any]:
    current = _manifest_rows(_load_json(current_manifest_path))
    staged = _manifest_rows(_load_json(staged_manifest_path))

    if set(current) != set(staged):
        raise SelectiveRebuildDeltaError(
            "El conjunto documental cambió durante staging"
        )

    deltas: list[DocumentDelta] = []
    for document_id in sorted(current):
        current_row = current[document_id]
        staged_row = staged[document_id]
        current_source = _required(
            current_row, "source_sha256", document_id
        ).casefold()
        staged_source = _required(
            staged_row, "source_sha256", document_id
        ).casefold()

        current_md = _find_normalized_for_document(
            current_normalized_root, document_id, current_row
        )
        staged_md = _find_normalized_for_document(
            staged_normalized_root, document_id, staged_row
        )
        current_md_sha = _sha(current_md)
        staged_md_sha = _sha(staged_md)
        deltas.append(
            DocumentDelta(
                document_id=document_id,
                current_source_sha256=current_source,
                staged_source_sha256=staged_source,
                source_changed=current_source != staged_source,
                current_normalized_sha256=current_md_sha,
                staged_normalized_sha256=staged_md_sha,
                normalized_changed=current_md_sha != staged_md_sha,
            )
        )

    changed_source = {
        item.document_id for item in deltas if item.source_changed
    }
    changed_normalized = {
        item.document_id for item in deltas if item.normalized_changed
    }
    unauthorized = (changed_source | changed_normalized) - AUTHORIZED
    authorized_complete = AUTHORIZED.issubset(changed_source)
    delta_safe = not unauthorized and authorized_complete

    report = {
        "sprint": "19I.18J.12.2",
        "mode": "delta_verification_fail_closed",
        "document_count": len(deltas),
        "authorized_documents": sorted(AUTHORIZED),
        "source_changed_documents": sorted(changed_source),
        "normalized_changed_documents": sorted(changed_normalized),
        "unauthorized_changed_documents": sorted(unauthorized),
        "authorized_source_replacements_complete": authorized_complete,
        "delta_safe_for_candidate_build": delta_safe,
        "canonical_mutation_performed": False,
        "runtime_index_mutated": False,
        "public_release_allowed": False,
        "git_push_allowed": False,
        "github_release_allowed": False,
        "render_deploy_allowed": False,
        "documents": [asdict(item) for item in deltas],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report
