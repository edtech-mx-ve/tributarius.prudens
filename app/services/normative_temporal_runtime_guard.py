from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class TemporalRuntimeGuardError(RuntimeError):
    """Error controlado al cargar la política temporal de runtime."""


@dataclass(frozen=True)
class TemporalRuntimeGuard:
    """Bloquea promoción normativa cuando la vigencia documental sigue desconocida."""

    blocked_documents: frozenset[str]
    schema_version: str
    source_sprint: str

    def blocks_document(self, document_id: str) -> bool:
        return document_id.casefold() in self.blocked_documents


def _as_dict(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TemporalRuntimeGuardError(f"{label} debe ser un objeto JSON.")
    return value


def _as_list(value: object, *, label: str) -> list[object]:
    if not isinstance(value, list):
        raise TemporalRuntimeGuardError(f"{label} debe ser una lista JSON.")
    return value


def _required_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TemporalRuntimeGuardError(f"Campo requerido inválido: {key}.")
    return value.strip()


def load_temporal_runtime_guard(path: Path) -> TemporalRuntimeGuard:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise TemporalRuntimeGuardError(
            f"No existe registro temporal de procedencia: {resolved}"
        )

    try:
        payload = _as_dict(
            json.loads(resolved.read_text(encoding="utf-8")),
            label="registro temporal",
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TemporalRuntimeGuardError(
            f"No se pudo leer el registro temporal: {resolved}"
        ) from exc

    schema_version = _required_str(payload, "schema_version")
    source_sprint = _required_str(payload, "source_sprint")
    gaps = _as_list(payload.get("coverage_gaps"), label="coverage_gaps")

    blocked: set[str] = set()
    for raw_gap in gaps:
        gap = _as_dict(raw_gap, label="coverage_gap")
        canonical_id = _required_str(gap, "canonical_id").casefold()
        gap_type = _required_str(gap, "gap_type")
        status = _required_str(gap, "status")
        if (
            gap_type == "document_wide_temporal_validity"
            and status == "unknown_fail_closed"
        ):
            blocked.add(canonical_id)

    return TemporalRuntimeGuard(
        blocked_documents=frozenset(blocked),
        schema_version=schema_version,
        source_sprint=source_sprint,
    )
