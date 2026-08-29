from __future__ import annotations

import csv
import json
import os
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.domain.legal_chunks import LegalChunk
from app.services.legal_identity_change_audit import audit_legal_identity_changes
from rag.chunking.legal_structurer import _detect_boundary


class LegalProfileBoundaryAuditError(RuntimeError):
    """Fallo controlado al auditar fronteras según el perfil real de chunking."""


@dataclass(frozen=True)
class ProfileBoundaryFinding:
    canonical_id: str
    baseline_chunk_id: str
    baseline_unit_type: str
    baseline_unit_label: str
    source_line: str
    chunking_profile: str
    actual_boundary_type: str | None
    actual_boundary_label: str | None
    baseline_identity_matches_actual_boundary: bool
    candidate_container_ids: tuple[str, ...]
    classification: str
    rationale: str


@dataclass(frozen=True)
class ProfileBoundaryReport:
    total_cases: int
    resolved_safe: int
    requires_review: int
    classifications: dict[str, int]
    findings: tuple[ProfileBoundaryFinding, ...]


def _load_json(path: Path) -> Any:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise LegalProfileBoundaryAuditError(f"No existe JSON requerido: {resolved}")
    try:
        return json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LegalProfileBoundaryAuditError(f"JSON inválido: {resolved}") from exc


def _load_chunks(path: Path) -> list[LegalChunk]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise LegalProfileBoundaryAuditError(f"No existe corpus: {resolved}")
    result: list[LegalChunk] = []
    with resolved.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                result.append(LegalChunk.model_validate_json(line))
            except ValueError as exc:
                raise LegalProfileBoundaryAuditError(
                    f"JSONL inválido en {resolved}:{line_number}"
                ) from exc
    return result


def _load_profiles(catalog_path: Path) -> dict[str, str]:
    payload = _load_json(catalog_path)
    if not isinstance(payload, list):
        raise LegalProfileBoundaryAuditError("El catálogo fiscal debe ser una lista.")
    profiles: dict[str, str] = {}
    for item in payload:
        if not isinstance(item, dict):
            raise LegalProfileBoundaryAuditError("Entrada inválida en catálogo fiscal.")
        canonical_id = str(item.get("canonical_id", "")).strip()
        profile = str(item.get("chunking_profile", "")).strip()
        if not canonical_id or not profile:
            raise LegalProfileBoundaryAuditError(
                "canonical_id/chunking_profile faltante en catálogo."
            )
        profiles[canonical_id] = profile
    return profiles


def _normalize_identity(unit_type: str, unit_label: str) -> tuple[str, str]:
    return unit_type, " ".join(unit_label.split()).casefold()


def audit_profile_boundaries(
    *,
    baseline_path: Path,
    candidate_path: Path,
    normalized_root: Path,
    catalog_path: Path,
) -> ProfileBoundaryReport:
    identity_report = audit_legal_identity_changes(
        baseline_path=baseline_path,
        candidate_path=candidate_path,
        normalized_root=normalized_root,
    )
    baseline = _load_chunks(baseline_path)
    baseline_by_id = {chunk.chunk_id: chunk for chunk in baseline}
    profiles = _load_profiles(catalog_path)

    targets = [
        finding
        for finding in identity_report.findings
        if finding.classification
        == "source_line_merged_under_neighbor_requires_review"
    ]

    findings: list[ProfileBoundaryFinding] = []
    for target in targets:
        old = baseline_by_id.get(target.baseline_chunk_id)
        if old is None:
            raise LegalProfileBoundaryAuditError(
                f"No existe chunk baseline: {target.baseline_chunk_id}"
            )

        profile = profiles.get(old.canonical_id)
        if profile is None:
            raise LegalProfileBoundaryAuditError(
                f"No existe perfil para {old.canonical_id}"
            )

        boundary = _detect_boundary(target.source_line, profile)
        actual_type = boundary[0].value if boundary else None
        actual_label = boundary[1] if boundary else None
        matches = (
            actual_type is not None
            and actual_label is not None
            and _normalize_identity(actual_type, actual_label)
            == _normalize_identity(old.unit_type.value, old.unit_label)
        )

        if boundary is None and target.candidate_container_ids:
            classification = "not_a_boundary_for_profile_text_preserved"
            rationale = (
                "La línea puede parecer heading genérico, pero el perfil real de "
                "chunking no la considera frontera; el texto permanece preservado."
            )
        elif matches:
            classification = "actual_boundary_missing_identity_requires_review"
            rationale = (
                "El perfil real sí detecta la misma frontera que 19C, pero la "
                "identidad no quedó preservada en el candidato."
            )
        elif boundary is not None:
            classification = "different_actual_boundary_requires_review"
            rationale = (
                "El perfil real detecta una frontera, pero su identidad difiere "
                "de la unidad 19C."
            )
        else:
            classification = "not_a_boundary_text_unverified_requires_review"
            rationale = (
                "El perfil real no detecta frontera y no hay contenedor candidato "
                "verificado."
            )

        findings.append(
            ProfileBoundaryFinding(
                canonical_id=old.canonical_id,
                baseline_chunk_id=old.chunk_id,
                baseline_unit_type=old.unit_type.value,
                baseline_unit_label=old.unit_label,
                source_line=target.source_line,
                chunking_profile=profile,
                actual_boundary_type=actual_type,
                actual_boundary_label=actual_label,
                baseline_identity_matches_actual_boundary=matches,
                candidate_container_ids=target.candidate_container_ids,
                classification=classification,
                rationale=rationale,
            )
        )

    counts = Counter(item.classification for item in findings)
    safe_class = "not_a_boundary_for_profile_text_preserved"
    resolved_safe = counts.get(safe_class, 0)
    return ProfileBoundaryReport(
        total_cases=len(findings),
        resolved_safe=resolved_safe,
        requires_review=len(findings) - resolved_safe,
        classifications=dict(sorted(counts.items())),
        findings=tuple(findings),
    )


def write_profile_boundary_outputs(
    *,
    output_dir: Path,
    report: ProfileBoundaryReport,
) -> None:
    resolved = output_dir.expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)

    json_path = resolved / "profile_boundary_audit.json"
    payload = json.dumps(
        asdict(report),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        delete=False,
        dir=resolved,
        prefix=".profile_boundary_audit.",
        suffix=".tmp",
    ) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    os.replace(temporary, json_path)

    csv_path = resolved / "profile_boundary_findings.csv"
    fields = (
        list(asdict(report.findings[0]).keys())
        if report.findings
        else [
            "canonical_id",
            "baseline_chunk_id",
            "baseline_unit_type",
            "baseline_unit_label",
            "source_line",
            "chunking_profile",
            "actual_boundary_type",
            "actual_boundary_label",
            "baseline_identity_matches_actual_boundary",
            "candidate_container_ids",
            "classification",
            "rationale",
        ]
    )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for finding in report.findings:
            row = asdict(finding)
            row["candidate_container_ids"] = "|".join(
                finding.candidate_container_ids
            )
            writer.writerow(row)
