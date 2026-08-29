from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.domain.chunks import LegalChunk
from app.services.legal_boundary_refinement import find_article_headings
from app.services.legal_unit_integrity import extract_article_identifier
from app.services.normative_integrity_audit import NormativeIntegrityAuditError
from rag.indexing.builder import IndexBuildError, load_chunks_jsonl


@dataclass(frozen=True)
class PrefixRepairFinding:
    chunk_id: str
    document_id: str
    source_unit_label: str | None
    metadata_article: str | None
    first_heading_article: str | None
    first_heading_offset: int | None
    prefix_chars: int
    repairable: bool
    reason: str
    prefix_excerpt: str
    repaired_excerpt: str | None


@dataclass(frozen=True)
class PrefixRepairPlan:
    created_at_utc: str
    input_path: str
    input_sha256: str
    total_chunks: int
    candidate_chunk_ids: tuple[str, ...]
    findings: tuple[PrefixRepairFinding, ...]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _excerpt(text: str, *, limit: int = 260) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"


def _metadata_article(chunk: LegalChunk) -> str | None:
    label = chunk.metadata.source_unit_label or chunk.metadata.legal_identifier
    return extract_article_identifier(label)


def analyze_prefix_repair(chunk: LegalChunk) -> PrefixRepairFinding:
    metadata_article = _metadata_article(chunk)
    headings = find_article_headings(chunk.text)
    first_heading = headings[0] if headings else None

    if metadata_article is None:
        return PrefixRepairFinding(
            chunk_id=chunk.chunk_id,
            document_id=chunk.metadata.document_id,
            source_unit_label=chunk.metadata.source_unit_label,
            metadata_article=None,
            first_heading_article=(
                first_heading.identifier if first_heading is not None else None
            ),
            first_heading_offset=(
                first_heading.start if first_heading is not None else None
            ),
            prefix_chars=0,
            repairable=False,
            reason="metadata_without_article",
            prefix_excerpt="",
            repaired_excerpt=None,
        )

    if first_heading is None:
        return PrefixRepairFinding(
            chunk_id=chunk.chunk_id,
            document_id=chunk.metadata.document_id,
            source_unit_label=chunk.metadata.source_unit_label,
            metadata_article=metadata_article,
            first_heading_article=None,
            first_heading_offset=None,
            prefix_chars=0,
            repairable=False,
            reason="no_strong_article_heading",
            prefix_excerpt=_excerpt(chunk.text),
            repaired_excerpt=None,
        )

    if first_heading.identifier != metadata_article:
        return PrefixRepairFinding(
            chunk_id=chunk.chunk_id,
            document_id=chunk.metadata.document_id,
            source_unit_label=chunk.metadata.source_unit_label,
            metadata_article=metadata_article,
            first_heading_article=first_heading.identifier,
            first_heading_offset=first_heading.start,
            prefix_chars=first_heading.start,
            repairable=False,
            reason="first_heading_does_not_match_metadata",
            prefix_excerpt=_excerpt(chunk.text[: first_heading.start]),
            repaired_excerpt=None,
        )

    if first_heading.start == 0:
        return PrefixRepairFinding(
            chunk_id=chunk.chunk_id,
            document_id=chunk.metadata.document_id,
            source_unit_label=chunk.metadata.source_unit_label,
            metadata_article=metadata_article,
            first_heading_article=first_heading.identifier,
            first_heading_offset=0,
            prefix_chars=0,
            repairable=False,
            reason="already_aligned",
            prefix_excerpt="",
            repaired_excerpt=_excerpt(chunk.text),
        )

    repaired_text = chunk.text[first_heading.start :].lstrip()
    return PrefixRepairFinding(
        chunk_id=chunk.chunk_id,
        document_id=chunk.metadata.document_id,
        source_unit_label=chunk.metadata.source_unit_label,
        metadata_article=metadata_article,
        first_heading_article=first_heading.identifier,
        first_heading_offset=first_heading.start,
        prefix_chars=first_heading.start,
        repairable=True,
        reason="prefix_contamination_before_matching_heading",
        prefix_excerpt=_excerpt(chunk.text[: first_heading.start]),
        repaired_excerpt=_excerpt(repaired_text),
    )


def build_prefix_repair_plan(
    *,
    input_path: Path,
    candidate_chunk_ids: Iterable[str],
) -> PrefixRepairPlan:
    resolved = input_path.expanduser().resolve()
    try:
        chunks = load_chunks_jsonl(resolved)
    except IndexBuildError as exc:
        raise NormativeIntegrityAuditError(str(exc)) from exc

    wanted = tuple(dict.fromkeys(candidate_chunk_ids))
    by_id = {chunk.chunk_id: chunk for chunk in chunks}
    missing = [chunk_id for chunk_id in wanted if chunk_id not in by_id]
    if missing:
        raise NormativeIntegrityAuditError(
            "No se encontraron chunks candidatos: " + ", ".join(missing)
        )

    findings = tuple(analyze_prefix_repair(by_id[chunk_id]) for chunk_id in wanted)
    return PrefixRepairPlan(
        created_at_utc=datetime.now(UTC).isoformat(),
        input_path=str(resolved),
        input_sha256=_sha256(resolved),
        total_chunks=len(chunks),
        candidate_chunk_ids=wanted,
        findings=findings,
    )


def apply_prefix_repair(
    *,
    input_path: Path,
    output_path: Path,
    candidate_chunk_ids: Iterable[str],
) -> PrefixRepairPlan:
    input_resolved = input_path.expanduser().resolve()
    output_resolved = output_path.expanduser().resolve()

    if input_resolved == output_resolved:
        raise NormativeIntegrityAuditError(
            "La salida debe ser distinta del corpus canónico de entrada."
        )
    if output_resolved.exists():
        raise NormativeIntegrityAuditError(
            f"La salida ya existe y no se sobrescribirá: {output_resolved}"
        )

    try:
        chunks = load_chunks_jsonl(input_resolved)
    except IndexBuildError as exc:
        raise NormativeIntegrityAuditError(str(exc)) from exc

    wanted = tuple(dict.fromkeys(candidate_chunk_ids))
    by_id = {chunk.chunk_id: chunk for chunk in chunks}
    missing = [chunk_id for chunk_id in wanted if chunk_id not in by_id]
    if missing:
        raise NormativeIntegrityAuditError(
            "No se encontraron chunks candidatos: " + ", ".join(missing)
        )

    findings = tuple(analyze_prefix_repair(by_id[chunk_id]) for chunk_id in wanted)
    not_repairable = [finding for finding in findings if not finding.repairable]
    if not_repairable:
        reasons = ", ".join(
            f"{finding.chunk_id}:{finding.reason}" for finding in not_repairable
        )
        raise NormativeIntegrityAuditError(
            "El plan contiene candidatos no reparables automáticamente: " + reasons
        )

    repaired_by_id: dict[str, LegalChunk] = {}
    for finding in findings:
        original = by_id[finding.chunk_id]
        if finding.first_heading_offset is None:
            raise NormativeIntegrityAuditError(
                f"Falta offset de encabezado para {finding.chunk_id}."
            )
        repaired_text = original.text[finding.first_heading_offset :].lstrip()
        repaired_by_id[finding.chunk_id] = original.model_copy(
            update={"text": repaired_text}
        )

    output_resolved.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        delete=False,
        dir=output_resolved.parent,
        prefix=f".{output_resolved.name}.",
        suffix=".tmp",
    ) as handle:
        for chunk in chunks:
            effective = repaired_by_id.get(chunk.chunk_id, chunk)
            handle.write(effective.model_dump_json())
            handle.write("\n")
        temp_path = Path(handle.name)

    os.replace(temp_path, output_resolved)

    try:
        repaired_chunks = load_chunks_jsonl(output_resolved)
    except IndexBuildError as exc:
        output_resolved.unlink(missing_ok=True)
        raise NormativeIntegrityAuditError(str(exc)) from exc

    if len(repaired_chunks) != len(chunks):
        output_resolved.unlink(missing_ok=True)
        raise NormativeIntegrityAuditError(
            "La copia reparada cambió la cardinalidad del corpus."
        )

    return PrefixRepairPlan(
        created_at_utc=datetime.now(UTC).isoformat(),
        input_path=str(input_resolved),
        input_sha256=_sha256(input_resolved),
        total_chunks=len(chunks),
        candidate_chunk_ids=wanted,
        findings=findings,
    )


def write_plan(path: Path, plan: PrefixRepairPlan) -> None:
    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(asdict(plan), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        delete=False,
        dir=resolved.parent,
        prefix=f".{resolved.name}.",
        suffix=".tmp",
    ) as handle:
        handle.write(payload)
        temp_path = Path(handle.name)
    os.replace(temp_path, resolved)
