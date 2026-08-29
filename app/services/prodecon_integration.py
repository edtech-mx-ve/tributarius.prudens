from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from app.domain.documents import DocumentMetadata, SourceType
from app.domain.prodecon import (
    ProdeconIntegrationManifest,
    ProdeconSectionResult,
    ProdeconSectionSpec,
)

PAGE_BLOCK_RE = re.compile(
    r"<!--\s*page:(?P<page>\d+)\s*-->\s*"
    r"##\s+P[áa]gina\s+\d+\s*(?P<body>.*?)(?=(?:\n<!--\s*page:\d+\s*-->)|\Z)",
    flags=re.IGNORECASE | re.DOTALL,
)


class ProdeconIntegrationError(RuntimeError):
    """Error controlado al estructurar el corpus PRODECON."""


def load_section_specs(path: Path) -> list[ProdeconSectionSpec]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ProdeconIntegrationError(f"No existe el mapeo PRODECON: {resolved}")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        specs = TypeAdapter(list[ProdeconSectionSpec]).validate_python(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ProdeconIntegrationError("El mapeo PRODECON no es válido.") from exc

    if len(specs) != 12:
        raise ProdeconIntegrationError("El mapeo debe contener exactamente 12 apartados.")
    if [item.order for item in specs] != list(range(1, 13)):
        raise ProdeconIntegrationError("Los apartados PRODECON deben estar ordenados del 1 al 12.")
    if len({item.section_id for item in specs}) != 12:
        raise ProdeconIntegrationError("Hay section_id duplicados en el mapeo.")
    return specs


def parse_pages(markdown: str) -> dict[int, str]:
    pages: dict[int, str] = {}
    for match in PAGE_BLOCK_RE.finditer(markdown):
        page = int(match.group("page"))
        body = match.group("body").strip()
        if page in pages:
            raise ProdeconIntegrationError(f"Página duplicada en Markdown: {page}")
        pages[page] = body
    if not pages:
        raise ProdeconIntegrationError("No se detectaron marcadores de página.")
    return pages


def _section_markdown(spec: ProdeconSectionSpec, pages: dict[int, str]) -> str:
    missing = [page for page in range(spec.page_start, spec.page_end + 1) if page not in pages]
    if missing:
        raise ProdeconIntegrationError(
            f"{spec.section_id}: faltan páginas en Markdown: {missing[:5]}"
        )

    parts = [
        f"# {spec.section_id} — {spec.title}",
        "",
        f"> Módulo funcional: `{spec.module_key}` — {spec.module_name}",
        "",
    ]
    for page in range(spec.page_start, spec.page_end + 1):
        body = pages[page].strip()
        parts.extend([f"<!-- page:{page} -->", f"## Página {page}", "", body, ""])
    text = "\n".join(parts).strip() + "\n"
    if len(text.strip()) < 100:
        raise ProdeconIntegrationError(f"{spec.section_id}: contenido insuficiente.")
    return text


def integrate_prodecon_sections(
    *,
    markdown_path: Path,
    metadata_path: Path,
    mapping_path: Path,
    output_dir: Path,
    manifest_path: Path,
    overwrite: bool = False,
) -> ProdeconIntegrationManifest:
    try:
        metadata = DocumentMetadata.model_validate_json(
            metadata_path.expanduser().resolve().read_text(encoding="utf-8")
        )
    except (OSError, ValidationError) as exc:
        raise ProdeconIntegrationError("Metadatos documentales inválidos.") from exc

    if metadata.source_type is not SourceType.PRODECON:
        raise ProdeconIntegrationError("El documento debe tener source_type=prodecon.")

    source_markdown = markdown_path.expanduser().resolve()
    if not source_markdown.is_file():
        raise ProdeconIntegrationError(f"No existe Markdown normalizado: {source_markdown}")
    text = source_markdown.read_text(encoding="utf-8")
    pages = parse_pages(text)
    specs = load_section_specs(mapping_path)

    target_dir = output_dir.expanduser().resolve()
    target_manifest = manifest_path.expanduser().resolve()
    targets = [target_dir / f"{spec.section_id.lower()}.md" for spec in specs]
    existing = [path for path in [*targets, target_manifest] if path.exists()]
    if existing and not overwrite:
        raise ProdeconIntegrationError(
            "Ya existen artefactos PRODECON; use overwrite=True para regenerarlos."
        )

    target_dir.mkdir(parents=True, exist_ok=True)
    target_manifest.parent.mkdir(parents=True, exist_ok=True)

    results: list[ProdeconSectionResult] = []
    warnings = list(metadata.warnings)
    for spec, target in zip(specs, targets, strict=True):
        section_text = _section_markdown(spec, pages)
        target.write_text(section_text, encoding="utf-8")
        digest = hashlib.sha256(section_text.encode("utf-8")).hexdigest()
        results.append(
            ProdeconSectionResult(
                section_id=spec.section_id,
                order=spec.order,
                title=spec.title,
                module_key=spec.module_key,
                module_name=spec.module_name,
                page_start=spec.page_start,
                page_end=spec.page_end,
                character_count=len(section_text),
                sha256=digest,
                output_path=str(target),
            )
        )

    manifest = ProdeconIntegrationManifest(
        source_document_id=metadata.document_id,
        source_sha256=metadata.sha256,
        source_filename=metadata.original_filename,
        section_count=len(results),
        sections=results,
        warnings=warnings,
    )
    target_manifest.write_text(
        json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest
