from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.domain.documents import SourceType
from app.domain.fiscal_corpus import (
    FiscalCorpusManifest,
    FiscalDocumentResult,
    FiscalDocumentSpec,
    KnowledgeLayer,
)
from app.services.document_pipeline import DocumentPipelineError, process_pdf


class FiscalCorpusIntegrationError(RuntimeError):
    """Error controlado durante la ingestión del corpus fiscal local."""


Processor = Callable[..., Any]


def load_catalog(path: Path) -> list[FiscalDocumentSpec]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FiscalCorpusIntegrationError(f"No existe el catálogo fiscal: {resolved}")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        specs = TypeAdapter(list[FiscalDocumentSpec]).validate_python(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise FiscalCorpusIntegrationError("El catálogo fiscal no es válido.") from exc

    if len(specs) != 15:
        raise FiscalCorpusIntegrationError(
            f"El catálogo Sprint 19B debe contener exactamente 15 documentos; recibió {len(specs)}."
        )
    ids = [item.canonical_id for item in specs]
    names = [item.filename.casefold() for item in specs]
    if len(ids) != len(set(ids)):
        raise FiscalCorpusIntegrationError("Hay canonical_id duplicados en el catálogo.")
    if len(names) != len(set(names)):
        raise FiscalCorpusIntegrationError("Hay filename duplicados en el catálogo.")
    return specs


def validate_corpus_inventory(
    corpus_dir: Path,
    specs: list[FiscalDocumentSpec],
) -> dict[str, Path]:
    root = corpus_dir.expanduser().resolve()
    if not root.is_dir():
        raise FiscalCorpusIntegrationError(f"No existe el directorio del corpus: {root}")

    available: dict[str, Path] = {}
    for path in root.iterdir():
        if path.is_file() and path.suffix.casefold() == ".pdf":
            key = path.name.casefold()
            if key in available:
                raise FiscalCorpusIntegrationError(f"PDF duplicado por nombre: {path.name}")
            available[key] = path

    missing = [spec.filename for spec in specs if spec.filename.casefold() not in available]
    if missing:
        raise FiscalCorpusIntegrationError(
            "Faltan PDF requeridos por Sprint 19B: " + ", ".join(sorted(missing))
        )

    return {spec.canonical_id: available[spec.filename.casefold()] for spec in specs}


def _slug(filename: str) -> str:
    return Path(filename).stem.lower().replace(" ", "-")


def _source_type(layer: KnowledgeLayer) -> SourceType:
    if layer is KnowledgeLayer.UNAM:
        return SourceType.UNAM
    return SourceType.NORMATIVA


def _atomic_json_write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    try:
        temp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        temp.replace(path)
    finally:
        if temp.exists():
            temp.unlink()


def _legal_metadata_payload(
    spec: FiscalDocumentSpec,
    *,
    document_id: str,
    source_sha256: str,
    normalized_path: str,
) -> dict[str, object]:
    payload = spec.model_dump(mode="json")
    payload.update(
        {
            "schema_version": "1.0",
            "document_id": document_id,
            "source_sha256": source_sha256,
            "normalized_path": normalized_path,
        }
    )
    return payload


def integrate_fiscal_corpus(
    *,
    corpus_dir: Path,
    catalog_path: Path,
    normalized_root: Path,
    metadata_dir: Path,
    legal_metadata_dir: Path,
    manifest_path: Path,
    overwrite: bool = False,
    processor: Processor = process_pdf,
) -> FiscalCorpusManifest:
    """Ingiere los 15 PDF de Sprint 19B y genera Markdown + metadatos.

    PRODECON se mantiene fuera de esta función porque fue integrado en Sprint 19A.
    La función realiza preflight completo antes de procesar el primer documento.
    """

    specs = load_catalog(catalog_path)
    inventory = validate_corpus_inventory(corpus_dir, specs)

    target_manifest = manifest_path.expanduser().resolve()
    target_metadata_dir = metadata_dir.expanduser().resolve()
    target_legal_dir = legal_metadata_dir.expanduser().resolve()
    target_normalized_root = normalized_root.expanduser().resolve()

    expected_paths: list[Path] = [target_manifest]
    for spec in specs:
        slug = _slug(spec.filename)
        layer_dir = target_normalized_root / spec.layer.value
        expected_paths.extend(
            [
                layer_dir / f"{slug}.md",
                target_metadata_dir / f"{slug}.json",
                target_legal_dir / f"{spec.canonical_id}.json",
            ]
        )

    existing = [path for path in expected_paths if path.exists()]
    if existing and not overwrite:
        preview = ", ".join(str(path) for path in existing[:5])
        raise FiscalCorpusIntegrationError(
            "Ya existen artefactos Sprint 19B; use --overwrite para regenerarlos. "
            f"Ejemplos: {preview}"
        )

    target_metadata_dir.mkdir(parents=True, exist_ok=True)
    target_legal_dir.mkdir(parents=True, exist_ok=True)
    target_normalized_root.mkdir(parents=True, exist_ok=True)

    results: list[FiscalDocumentResult] = []
    corpus_warnings: list[str] = []

    for spec in specs:
        pdf_path = inventory[spec.canonical_id]
        layer_dir = target_normalized_root / spec.layer.value
        layer_dir.mkdir(parents=True, exist_ok=True)

        try:
            processed = processor(
                input_path=pdf_path,
                source_type=_source_type(spec.layer),
                output_dir=layer_dir,
                metadata_dir=target_metadata_dir,
            )
        except (DocumentPipelineError, OSError, ValueError) as exc:
            raise FiscalCorpusIntegrationError(
                f"Falló la ingestión de {spec.filename}: {exc}"
            ) from exc

        metadata = processed.metadata
        normalized_path = str(metadata.normalized_path)
        legal_path = target_legal_dir / f"{spec.canonical_id}.json"
        _atomic_json_write(
            legal_path,
            _legal_metadata_payload(
                spec,
                document_id=metadata.document_id,
                source_sha256=metadata.sha256,
                normalized_path=normalized_path,
            ),
        )

        warnings = list(metadata.warnings)
        if warnings:
            corpus_warnings.extend(f"{spec.canonical_id}: {item}" for item in warnings)

        results.append(
            FiscalDocumentResult(
                canonical_id=spec.canonical_id,
                filename=spec.filename,
                document_id=metadata.document_id,
                source_sha256=metadata.sha256,
                layer=spec.layer,
                source_role=spec.source_role,
                normalized_path=normalized_path,
                metadata_path=str(target_metadata_dir / f"{_slug(spec.filename)}.json"),
                legal_metadata_path=str(legal_path),
                page_count=metadata.stats.page_count,
                extracted_characters=metadata.stats.extracted_characters,
                empty_pages=metadata.stats.empty_pages,
                warnings=warnings,
            )
        )

    manifest = FiscalCorpusManifest(
        document_count=len(results),
        documents=results,
        warnings=corpus_warnings,
    )
    _atomic_json_write(
        target_manifest,
        manifest.model_dump(mode="json"),
    )
    return manifest
