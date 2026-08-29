from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.domain.legal_chunks import (
    ChunkingDocumentSummary,
    LegalChunk,
    LegalChunkingManifest,
)
from rag.chunking.legal_structurer import (
    stable_chunk_id,
    structure_document,
    structure_prodecon_sections,
    text_sha256,
)


class CorpusChunkingError(RuntimeError):
    """Error controlado durante la estructuración jurídica del corpus."""


def _load_json(path: Path) -> Any:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise CorpusChunkingError(f"No existe el archivo requerido: {resolved}")
    try:
        return json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CorpusChunkingError(f"JSON inválido: {resolved}") from exc


def _resolve_existing_path(raw: str, *, project_root: Path) -> Path:
    candidate = Path(raw)
    if candidate.is_file():
        return candidate.resolve()

    # Los manifiestos 19A/19B pueden contener rutas absolutas locales.
    # Si el proyecto se movió, recuperamos el archivo por basename dentro de knowledge/.
    for base in (
        project_root / "knowledge" / "normalized" / "normativa",
        project_root / "knowledge" / "normalized" / "unam",
        project_root / "knowledge" / "normalized" / "prodecon" / "sections",
    ):
        fallback = base / candidate.name
        if fallback.is_file():
            return fallback.resolve()
    raise CorpusChunkingError(f"No existe Markdown normalizado: {raw}")


def _read_text(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CorpusChunkingError(f"No se pudo leer {path}") from exc
    if not text.strip():
        raise CorpusChunkingError(f"Markdown vacío: {path}")
    return text


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    try:
        temp.write_text(content, encoding="utf-8")
        temp.replace(path)
    finally:
        if temp.exists():
            temp.unlink()


def _metadata_from_spec(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_role": str(spec["source_role"]),
        "document_type": str(spec["document_type"]),
        "matter": list(spec.get("matter", [])),
        "jurisdiction": str(spec.get("jurisdiction", "México")),
        "fiscal_year": spec.get("fiscal_year"),
        "publication_date": spec.get("publication_date"),
        "last_reform_date": spec.get("last_reform_date"),
        "effective_from": spec.get("effective_from"),
        "effective_to": spec.get("effective_to"),
    }


def _make_chunks(
    *,
    canonical_id: str,
    title: str,
    source_sha256: str,
    metadata: dict[str, Any],
    units: list[Any],
) -> list[LegalChunk]:
    chunks: list[LegalChunk] = []
    for ordinal, unit in enumerate(units, start=1):
        chunks.append(
            LegalChunk(
                chunk_id=stable_chunk_id(
                    canonical_id,
                    unit.unit_type,
                    unit.label,
                    unit.text,
                    ordinal=ordinal,
                ),
                canonical_id=canonical_id,
                source_role=metadata["source_role"],
                document_type=metadata["document_type"],
                title=title,
                unit_type=unit.unit_type,
                unit_label=unit.label,
                hierarchy=list(unit.hierarchy),
                page_start=unit.page_start,
                page_end=unit.page_end,
                fiscal_year=metadata["fiscal_year"],
                source_sha256=source_sha256,
                text_sha256=text_sha256(unit.text),
                text=unit.text,
                matter=metadata["matter"],
                jurisdiction=metadata["jurisdiction"],
                publication_date=metadata["publication_date"],
                last_reform_date=metadata["last_reform_date"],
                effective_from=metadata["effective_from"],
                effective_to=metadata["effective_to"],
            )
        )
    if not chunks:
        raise CorpusChunkingError(f"No se generaron chunks para {canonical_id}")
    return chunks


def _load_catalog_by_id(catalog_path: Path) -> dict[str, dict[str, Any]]:
    payload = _load_json(catalog_path)
    if not isinstance(payload, list):
        raise CorpusChunkingError("El catálogo 19B debe ser una lista JSON.")
    by_id: dict[str, dict[str, Any]] = {}
    for item in payload:
        if not isinstance(item, dict) or "canonical_id" not in item:
            raise CorpusChunkingError("Entrada inválida en catálogo 19B.")
        canonical_id = str(item["canonical_id"])
        if canonical_id in by_id:
            raise CorpusChunkingError(f"canonical_id duplicado: {canonical_id}")
        by_id[canonical_id] = item
    return by_id


def build_legal_chunks(
    *,
    project_root: Path,
    catalog_path: Path,
    fiscal_manifest_path: Path,
    prodecon_manifest_path: Path,
    chunks_path: Path,
    manifest_path: Path,
    overwrite: bool = False,
) -> LegalChunkingManifest:
    root = project_root.expanduser().resolve()
    catalog = _load_catalog_by_id(catalog_path)
    fiscal_manifest = _load_json(fiscal_manifest_path)
    prodecon_manifest = _load_json(prodecon_manifest_path)

    if fiscal_manifest.get("document_count") != 15:
        raise CorpusChunkingError("Sprint 19B debe aportar exactamente 15 documentos.")
    if prodecon_manifest.get("section_count") != 12:
        raise CorpusChunkingError("Sprint 19A debe aportar exactamente 12 secciones PRODECON.")

    output_chunks = chunks_path.expanduser().resolve()
    output_manifest = manifest_path.expanduser().resolve()
    if not overwrite and (output_chunks.exists() or output_manifest.exists()):
        raise CorpusChunkingError(
            "Ya existen artefactos 19C. Use --overwrite para regenerarlos deliberadamente."
        )

    all_chunks: list[LegalChunk] = []
    summaries: list[ChunkingDocumentSummary] = []
    warnings: list[str] = []

    # 15 documentos de Sprint 19B.
    for document in fiscal_manifest["documents"]:
        canonical_id = str(document["canonical_id"])
        spec = catalog.get(canonical_id)
        if spec is None:
            raise CorpusChunkingError(f"No existe especificación para {canonical_id}")

        normalized = _resolve_existing_path(str(document["normalized_path"]), project_root=root)
        text = _read_text(normalized)
        profile = str(spec["chunking_profile"])
        units = structure_document(text, profile=profile)
        if canonical_id == "manual_derecho_fiscal_unam" and len(units) != 7:
            raise CorpusChunkingError(
                "Manual Derecho Fiscal UNAM debe producir exactamente 7 capítulos; "
                f"detectados={len(units)}."
            )
        metadata = _metadata_from_spec(spec)
        chunks = _make_chunks(
            canonical_id=canonical_id,
            title=str(spec["title"]),
            source_sha256=str(document["source_sha256"]),
            metadata=metadata,
            units=units,
        )
        all_chunks.extend(chunks)
        fallback_count = sum(1 for unit in units if unit.used_fallback)
        structured_count = len(units) - fallback_count
        summaries.append(
            ChunkingDocumentSummary(
                canonical_id=canonical_id,
                profile=profile,
                chunks=len(chunks),
                structured_chunks=structured_count,
                fallback_chunks=fallback_count,
                characters=sum(len(item.text) for item in chunks),
            )
        )
        if fallback_count:
            warnings.append(
                f"{canonical_id}: {fallback_count} chunk(s) usaron fallback estructural."
            )

    # PRODECON: cada una de sus 12 secciones es una unidad recuperable explícita.
    section_inputs: list[tuple[str, str, int | None, int | None]] = []
    for section in prodecon_manifest["sections"]:
        section_path = _resolve_existing_path(str(section["output_path"]), project_root=root)
        section_inputs.append(
            (
                f'{section["section_id"]} — {section["title"]}',
                _read_text(section_path),
                int(section["page_start"]),
                int(section["page_end"]),
            )
        )

    prodecon_units = structure_prodecon_sections(section_inputs)
    prodecon_metadata = {
        "source_role": "orientacion",
        "document_type": "guia_contribuyente",
        "matter": ["orientacion_contribuyente", "derechos_obligaciones", "fiscal_general"],
        "jurisdiction": "México",
        "fiscal_year": None,
        "publication_date": None,
        "last_reform_date": None,
        "effective_from": None,
        "effective_to": None,
    }
    prodecon_chunks = _make_chunks(
        canonical_id="prodecon_contribuyente",
        title="Lo que todo contribuyente debe saber",
        source_sha256=str(prodecon_manifest["source_sha256"]),
        metadata=prodecon_metadata,
        units=prodecon_units,
    )
    all_chunks.extend(prodecon_chunks)
    summaries.append(
        ChunkingDocumentSummary(
            canonical_id="prodecon_contribuyente",
            profile="prodecon_section",
            chunks=len(prodecon_chunks),
            structured_chunks=len(prodecon_chunks),
            fallback_chunks=0,
            characters=sum(len(item.text) for item in prodecon_chunks),
        )
    )

    ids = [chunk.chunk_id for chunk in all_chunks]
    if len(ids) != len(set(ids)):
        seen: set[str] = set()
        duplicates: list[str] = []
        for chunk_id in ids:
            if chunk_id in seen and chunk_id not in duplicates:
                duplicates.append(chunk_id)
            seen.add(chunk_id)
        preview = ", ".join(duplicates[:5])
        raise CorpusChunkingError(
            f"Se detectaron chunk_id duplicados: {preview}"
        )

    lines = [json.dumps(chunk.model_dump(mode="json"), ensure_ascii=False) for chunk in all_chunks]
    jsonl = "\n".join(lines) + "\n"
    chunks_digest = hashlib.sha256(jsonl.encode("utf-8")).hexdigest()

    manifest = LegalChunkingManifest(
        document_count=len(summaries),
        chunk_count=len(all_chunks),
        chunks_sha256=chunks_digest,
        documents=summaries,
        warnings=warnings,
    )

    _atomic_write(output_chunks, jsonl)
    _atomic_write(
        output_manifest,
        json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
    )
    return manifest
