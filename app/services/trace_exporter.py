from __future__ import annotations

import json
from pathlib import Path

from app.domain.traceability import CanonicalExecutionResult


class TraceExportError(ValueError):
    """Error controlado de exportación de trazabilidad."""


def export_canonical_json(
    result: CanonicalExecutionResult,
    output_path: Path,
    *,
    overwrite: bool = False,
) -> Path:
    resolved = output_path.expanduser().resolve()
    if resolved.suffix.lower() != ".json":
        raise TraceExportError("La trazabilidad canónica debe exportarse como JSON.")
    if resolved.exists() and not overwrite:
        raise TraceExportError(
            f"El archivo ya existe y no se sobrescribirá: {resolved.name}"
        )
    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        temporary = resolved.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(
                result.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        temporary.replace(resolved)
    except OSError as exc:
        raise TraceExportError("No fue posible exportar la trazabilidad.") from exc
    return resolved
