from __future__ import annotations

import csv
import json
import os
import re
import tempfile
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.services.normative_integrity_audit import (
    NormativeIntegrityAuditError,
    run_audit,
)


class NormativeTemporalEvidenceAuditError(RuntimeError):
    """Fallo controlado durante auditoría de evidencia temporal normativa."""


def _summary_int(summary: Mapping[str, object], key: str) -> int:
    value = summary.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise NormativeTemporalEvidenceAuditError(
            f"Resumen temporal inválido para {key!r}: {value!r}."
        )
    return value


_TEMPORAL_SIGNAL_RE = re.compile(
    r"\b("
    r"entrar[aá]\s+en\s+vigor|"
    r"entra\s+en\s+vigor|"
    r"vigencia|"
    r"transitorio(?:s)?|"
    r"efectos?\s+a\s+partir\s+de|"
    r"surtir[aá]\s+efectos|"
    r"publicaci[oó]n\s+en\s+el\s+diario\s+oficial"
    r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TemporalDocumentSummary:
    canonical_id: str
    normative_chunks: int
    temporal_bounded: int
    temporal_open_end: int
    temporal_open_start: int
    temporal_unknown: int
    temporal_invalid: int
    promotion_eligible: int
    temporal_coverage_ratio: float
    status: str


@dataclass(frozen=True)
class TemporalEvidenceLine:
    canonical_id: str
    source_path: str
    line_number: int
    line: str


@dataclass(frozen=True)
class TemporalEvidenceReport:
    runtime_chunks: int
    normative_chunks: int
    normative_documents: int
    temporal_known: int
    temporal_unknown: int
    temporal_invalid: int
    promotion_eligible: int
    priority_unknown_documents: tuple[str, ...]
    documents: tuple[TemporalDocumentSummary, ...]
    evidence_lines: tuple[TemporalEvidenceLine, ...]


def _load_catalog(path: Path) -> list[dict[str, Any]]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise NormativeTemporalEvidenceAuditError(
            f"No existe catálogo fiscal: {resolved}"
        )
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NormativeTemporalEvidenceAuditError(
            f"Catálogo fiscal inválido: {resolved}"
        ) from exc
    if not isinstance(payload, list):
        raise NormativeTemporalEvidenceAuditError(
            "El catálogo fiscal debe ser una lista JSON."
        )
    return [item for item in payload if isinstance(item, dict)]


def _normalized_path(root: Path, canonical_id: str) -> Path | None:
    direct = root / f"{canonical_id}.md"
    if direct.is_file():
        return direct
    folded = canonical_id.casefold()
    for path in root.glob("*.md"):
        if path.stem.casefold() == folded:
            return path
    return None


def _extract_evidence_lines(
    *,
    normalized_root: Path,
    document_ids: set[str],
    limit_per_document: int = 40,
) -> list[TemporalEvidenceLine]:
    root = normalized_root.expanduser().resolve()
    findings: list[TemporalEvidenceLine] = []
    for canonical_id in sorted(document_ids):
        path = _normalized_path(root, canonical_id)
        if path is None:
            continue
        found = 0
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise NormativeTemporalEvidenceAuditError(
                f"No se pudo leer fuente normalizada: {path}"
            ) from exc
        for line_number, raw in enumerate(lines, start=1):
            clean = " ".join(raw.split())
            if not clean or _TEMPORAL_SIGNAL_RE.search(clean) is None:
                continue
            findings.append(
                TemporalEvidenceLine(
                    canonical_id=canonical_id,
                    source_path=str(path),
                    line_number=line_number,
                    line=clean[:1200],
                )
            )
            found += 1
            if found >= limit_per_document:
                break
    return findings


def _document_status(
    *,
    normative_chunks: int,
    unknown: int,
    invalid: int,
) -> str:
    if invalid:
        return "temporal_invalid_requires_review"
    if normative_chunks <= 0:
        return "no_normative_chunks"
    if unknown == 0:
        return "temporal_metadata_complete"
    if unknown == normative_chunks:
        return "temporal_metadata_unknown"
    return "temporal_metadata_partial"


def audit_temporal_evidence(
    *,
    runtime_chunks_path: Path,
    normalized_root: Path,
    catalog_path: Path,
    audit_output_dir: Path,
    expected_total_chunks: int = 29326,
    priority_documents: tuple[str, ...] = ("liva", "cpeum"),
) -> TemporalEvidenceReport:
    # Materializa también las salidas 19I.3 sobre el nuevo runtime semántico.
    try:
        _findings, summary, _outputs = run_audit(
            input_path=runtime_chunks_path,
            output_dir=audit_output_dir,
        )
    except NormativeIntegrityAuditError as exc:
        raise NormativeTemporalEvidenceAuditError(str(exc)) from exc

    total_chunks = _summary_int(summary, "total_chunks")
    if expected_total_chunks and total_chunks != expected_total_chunks:
        raise NormativeTemporalEvidenceAuditError(
            f"Cardinalidad inesperada: {total_chunks}; "
            f"esperado={expected_total_chunks}."
        )

    catalog = _load_catalog(catalog_path)
    normative_catalog_ids = {
        str(item.get("canonical_id"))
        for item in catalog
        if item.get("layer") == "normativa" and item.get("canonical_id")
    }

    by_document_raw = summary.get("by_document")
    if not isinstance(by_document_raw, dict):
        raise NormativeTemporalEvidenceAuditError(
            "Resumen normativo sin desglose by_document."
        )

    documents: list[TemporalDocumentSummary] = []
    unknown_docs: set[str] = set()
    for canonical_id, raw_counts in sorted(by_document_raw.items()):
        if not isinstance(raw_counts, dict):
            continue
        normative_chunks = int(raw_counts.get("normative_chunks", 0))
        bounded = int(raw_counts.get("temporal_bounded", 0))
        open_end = int(raw_counts.get("temporal_open_end", 0))
        open_start = int(raw_counts.get("temporal_open_start", 0))
        unknown = int(raw_counts.get("temporal_unknown", 0))
        invalid = int(raw_counts.get("temporal_invalid", 0))
        eligible = int(raw_counts.get("promotion_eligible", 0))
        known = bounded + open_end + open_start
        ratio = known / normative_chunks if normative_chunks else 0.0
        if unknown:
            unknown_docs.add(canonical_id)
        documents.append(
            TemporalDocumentSummary(
                canonical_id=canonical_id,
                normative_chunks=normative_chunks,
                temporal_bounded=bounded,
                temporal_open_end=open_end,
                temporal_open_start=open_start,
                temporal_unknown=unknown,
                temporal_invalid=invalid,
                promotion_eligible=eligible,
                temporal_coverage_ratio=round(ratio, 6),
                status=_document_status(
                    normative_chunks=normative_chunks,
                    unknown=unknown,
                    invalid=invalid,
                ),
            )
        )

    target_docs = unknown_docs & normative_catalog_ids
    evidence_lines = _extract_evidence_lines(
        normalized_root=normalized_root,
        document_ids=target_docs,
    )
    priority_unknown = tuple(
        item for item in priority_documents if item in unknown_docs
    )

    bounded = _summary_int(summary, "temporal_bounded")
    open_end = _summary_int(summary, "temporal_open_end")
    open_start = _summary_int(summary, "temporal_open_start")
    return TemporalEvidenceReport(
        runtime_chunks=total_chunks,
        normative_chunks=_summary_int(summary, "normative_chunks"),
        normative_documents=_summary_int(summary, "normative_documents"),
        temporal_known=bounded + open_end + open_start,
        temporal_unknown=_summary_int(summary, "temporal_unknown"),
        temporal_invalid=_summary_int(summary, "temporal_invalid"),
        promotion_eligible=_summary_int(summary, "promotion_eligible"),
        priority_unknown_documents=priority_unknown,
        documents=tuple(documents),
        evidence_lines=tuple(evidence_lines),
    )


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        delete=False,
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def write_temporal_evidence_outputs(
    *,
    output_dir: Path,
    report: TemporalEvidenceReport,
) -> dict[str, Path]:
    resolved = output_dir.expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)

    report_path = resolved / "temporal_evidence_report.json"
    docs_path = resolved / "temporal_document_summary.csv"
    evidence_path = resolved / "temporal_evidence_lines.csv"

    _atomic_write(
        report_path,
        json.dumps(
            asdict(report),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )

    doc_fields = list(asdict(report.documents[0]).keys()) if report.documents else []
    if doc_fields:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8-sig",
            newline="",
            delete=False,
            dir=resolved,
            prefix=".temporal_document_summary.",
            suffix=".tmp",
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=doc_fields)
            writer.writeheader()
            for item in report.documents:
                writer.writerow(asdict(item))
            temp = Path(handle.name)
        os.replace(temp, docs_path)
    else:
        _atomic_write(docs_path, "")

    evidence_fields = (
        list(asdict(report.evidence_lines[0]).keys())
        if report.evidence_lines
        else ["canonical_id", "source_path", "line_number", "line"]
    )
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8-sig",
        newline="",
        delete=False,
        dir=resolved,
        prefix=".temporal_evidence_lines.",
        suffix=".tmp",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=evidence_fields)
        writer.writeheader()
        for evidence_item in report.evidence_lines:
            writer.writerow(asdict(evidence_item))
        temp = Path(handle.name)
    os.replace(temp, evidence_path)

    return {
        "report": report_path,
        "documents": docs_path,
        "evidence_lines": evidence_path,
    }
