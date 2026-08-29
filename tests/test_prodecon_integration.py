import json
from pathlib import Path

import pytest

from app.domain.documents import DocumentMetadata, ExtractionStats, SourceType
from app.services.prodecon_integration import (
    ProdeconIntegrationError,
    integrate_prodecon_sections,
    load_section_specs,
    parse_pages,
)


def _mapping(path: Path) -> None:
    rows = []
    start = 1
    for order in range(1, 13):
        rows.append(
            {
                "section_id": f"PRODECON-{order:02d}",
                "order": order,
                "title": f"Apartado {order}",
                "page_start": start,
                "page_end": start,
                "module_key": f"modulo_{order}",
                "module_name": f"Módulo {order}",
            }
        )
        start += 1
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")


def _metadata(path: Path) -> None:
    metadata = DocumentMetadata(
        document_id="prodecon-1234567890abcdef",
        source_type=SourceType.PRODECON,
        original_filename="prodecon.pdf",
        source_path="C:/privado/prodecon.pdf",
        normalized_path="knowledge/normalized/prodecon/prodecon.md",
        sha256="a" * 64,
        processed_at_utc="2026-08-29T00:00:00+00:00",
        extractor="pypdf",
        extractor_version="5.9.0",
        stats=ExtractionStats(
            page_count=12,
            extracted_characters=1200,
            empty_pages=0,
            heading_count=12,
        ),
    )
    path.write_text(metadata.model_dump_json(), encoding="utf-8")


def _markdown() -> str:
    return "\n".join(
        f"<!-- page:{page} -->\n## Página {page}\n\n"
        + ("Contenido fiscal de prueba " * 8)
        for page in range(1, 13)
    )


def test_mapping_requires_exactly_twelve_sections(tmp_path: Path) -> None:
    mapping = tmp_path / "mapping.json"
    _mapping(mapping)
    assert len(load_section_specs(mapping)) == 12

    rows = json.loads(mapping.read_text(encoding="utf-8"))
    mapping.write_text(json.dumps(rows[:-1]), encoding="utf-8")
    with pytest.raises(ProdeconIntegrationError, match="exactamente 12"):
        load_section_specs(mapping)


def test_parse_pages_preserves_page_markers() -> None:
    pages = parse_pages(_markdown())
    assert sorted(pages) == list(range(1, 13))
    assert "Contenido fiscal" in pages[1]


def test_integration_generates_manifest_and_twelve_sections(tmp_path: Path) -> None:
    mapping = tmp_path / "mapping.json"
    metadata = tmp_path / "metadata.json"
    markdown = tmp_path / "document.md"
    _mapping(mapping)
    _metadata(metadata)
    markdown.write_text(_markdown(), encoding="utf-8")

    manifest = integrate_prodecon_sections(
        markdown_path=markdown,
        metadata_path=metadata,
        mapping_path=mapping,
        output_dir=tmp_path / "sections",
        manifest_path=tmp_path / "manifest.json",
    )

    assert manifest.section_count == 12
    assert manifest.source_document_id == "prodecon-1234567890abcdef"
    assert len(list((tmp_path / "sections").glob("*.md"))) == 12
    assert (tmp_path / "manifest.json").is_file()


def test_integration_rejects_wrong_source_type(tmp_path: Path) -> None:
    mapping = tmp_path / "mapping.json"
    metadata = tmp_path / "metadata.json"
    markdown = tmp_path / "document.md"
    _mapping(mapping)
    _metadata(metadata)
    payload = json.loads(metadata.read_text(encoding="utf-8"))
    payload["source_type"] = "normativa"
    metadata.write_text(json.dumps(payload), encoding="utf-8")
    markdown.write_text(_markdown(), encoding="utf-8")

    with pytest.raises(ProdeconIntegrationError, match="source_type=prodecon"):
        integrate_prodecon_sections(
            markdown_path=markdown,
            metadata_path=metadata,
            mapping_path=mapping,
            output_dir=tmp_path / "sections",
            manifest_path=tmp_path / "manifest.json",
        )


def test_integration_refuses_silent_overwrite(tmp_path: Path) -> None:
    mapping = tmp_path / "mapping.json"
    metadata = tmp_path / "metadata.json"
    markdown = tmp_path / "document.md"
    _mapping(mapping)
    _metadata(metadata)
    markdown.write_text(_markdown(), encoding="utf-8")

    kwargs = dict(
        markdown_path=markdown,
        metadata_path=metadata,
        mapping_path=mapping,
        output_dir=tmp_path / "sections",
        manifest_path=tmp_path / "manifest.json",
    )
    integrate_prodecon_sections(**kwargs)
    with pytest.raises(ProdeconIntegrationError, match="Ya existen artefactos"):
        integrate_prodecon_sections(**kwargs)
