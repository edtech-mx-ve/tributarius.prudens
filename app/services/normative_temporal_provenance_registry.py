from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


class NormativeTemporalProvenanceRegistryError(RuntimeError):
    """Error controlado al construir el registro de procedencia temporal."""


@dataclass(frozen=True)
class TemporalProvenanceEntry:
    canonical_id: str
    source_path: str
    source_line: int
    explicit_date_signal: str
    evidence_classification: str
    scope_classification: str
    scope_reason: str
    document_wide_applicable: bool
    promotion_status: str
    effective_from: None = None
    effective_to: None = None


@dataclass(frozen=True)
class TemporalCoverageGap:
    canonical_id: str
    gap_type: str
    status: str
    reason: str


@dataclass(frozen=True)
class TemporalProvenanceRegistry:
    schema_version: str
    source_sprint: str
    policy: str
    entries: tuple[TemporalProvenanceEntry, ...]
    coverage_gaps: tuple[TemporalCoverageGap, ...]


def _require_dict(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise NormativeTemporalProvenanceRegistryError(
            f"{label} debe ser un objeto JSON."
        )
    return value


def _require_list(value: object, *, label: str) -> list[object]:
    if not isinstance(value, list):
        raise NormativeTemporalProvenanceRegistryError(
            f"{label} debe ser una lista JSON."
        )
    return value


def _require_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise NormativeTemporalProvenanceRegistryError(
            f"Campo requerido inválido: {key}."
        )
    return value.strip()


def _require_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise NormativeTemporalProvenanceRegistryError(
            f"Campo entero requerido inválido: {key}."
        )
    return value


def build_registry_from_verification(
    *,
    verification_report_path: Path,
    priority_documents: tuple[str, ...] = ("liva", "cpeum"),
) -> TemporalProvenanceRegistry:
    path = verification_report_path.expanduser().resolve()
    if not path.is_file():
        raise NormativeTemporalProvenanceRegistryError(
            f"No existe reporte 19I.13: {path}"
        )

    try:
        root = _require_dict(
            json.loads(path.read_text(encoding="utf-8")),
            label="reporte 19I.13",
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise NormativeTemporalProvenanceRegistryError(
            f"No se pudo leer reporte 19I.13: {path}"
        ) from exc

    raw_records = _require_list(root.get("records"), label="records")
    entries: list[TemporalProvenanceEntry] = []
    seen_documents: set[str] = set()

    for raw in raw_records:
        item = _require_dict(raw, label="record")
        canonical_id = _require_str(item, "canonical_id").casefold()
        scope = _require_str(item, "scope_classification")
        if scope not in {
            "whole_document_candidate",
            "amendment_specific_candidate",
            "ambiguous_scope_candidate",
        }:
            raise NormativeTemporalProvenanceRegistryError(
                f"scope_classification desconocido: {scope}"
            )

        document_wide = False
        if scope == "whole_document_candidate":
            promotion_status = "requires_human_verification_document_scope"
        elif scope == "amendment_specific_candidate":
            promotion_status = "blocked_scope_specific"
        else:
            promotion_status = "blocked_scope_ambiguous"

        entries.append(
            TemporalProvenanceEntry(
                canonical_id=canonical_id,
                source_path=_require_str(item, "source_path"),
                source_line=_require_int(item, "line_number"),
                explicit_date_signal=_require_str(item, "explicit_date_signal"),
                evidence_classification=_require_str(item, "classification"),
                scope_classification=scope,
                scope_reason=_require_str(item, "scope_reason"),
                document_wide_applicable=document_wide,
                promotion_status=promotion_status,
            )
        )
        seen_documents.add(canonical_id)

    gaps: list[TemporalCoverageGap] = []
    for canonical_id in priority_documents:
        normalized = canonical_id.casefold()
        if normalized not in seen_documents:
            reason = (
                "No se detectó fecha explícita candidata en la evidencia prioritaria."
            )
        else:
            reason = (
                "Existen candidatos temporales, pero ninguno está verificado como "
                "vigencia documental completa."
            )
        gaps.append(
            TemporalCoverageGap(
                canonical_id=normalized,
                gap_type="document_wide_temporal_validity",
                status="unknown_fail_closed",
                reason=reason,
            )
        )

    return TemporalProvenanceRegistry(
        schema_version="1.0",
        source_sprint="19I.13",
        policy=(
            "No se deriva vigencia documental desde publicación, última reforma "
            "ni disposiciones de alcance específico. effective_from/effective_to "
            "permanecen nulos hasta verificación jurídica de alcance."
        ),
        entries=tuple(entries),
        coverage_gaps=tuple(gaps),
    )


def write_registry(
    *,
    output_path: Path,
    registry: TemporalProvenanceRegistry,
) -> Path:
    path = output_path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        asdict(registry),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        delete=False,
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    os.replace(temporary, path)
    return path


def validate_fail_closed_registry(registry: TemporalProvenanceRegistry) -> None:
    for entry in registry.entries:
        if entry.effective_from is not None or entry.effective_to is not None:
            raise NormativeTemporalProvenanceRegistryError(
                "El registro 19I.14 no puede promover fechas efectivas."
            )
        if entry.document_wide_applicable:
            raise NormativeTemporalProvenanceRegistryError(
                "19I.14 no autoriza vigencia documental automática."
            )
    for gap in registry.coverage_gaps:
        if gap.status != "unknown_fail_closed":
            raise NormativeTemporalProvenanceRegistryError(
                "Todo gap prioritario debe permanecer fail-closed."
            )
