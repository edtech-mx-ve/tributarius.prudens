from __future__ import annotations

import argparse
import logging
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.domain.documents import SourceType
from app.services.document_pipeline import DocumentPipelineError, process_pdf
from app.services.prodecon_integration import (
    ProdeconIntegrationError,
    integrate_prodecon_sections,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Integra los 12 apartados de PRODECON en el corpus local."
    )
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument(
        "--mapping",
        type=Path,
        default=Path("knowledge/metadata/prodecon_12_mapping.json"),
    )
    parser.add_argument(
        "--normalized-dir",
        type=Path,
        default=Path("knowledge/normalized/prodecon"),
    )
    parser.add_argument(
        "--metadata-dir",
        type=Path,
        default=Path("knowledge/metadata"),
    )
    parser.add_argument(
        "--sections-dir",
        type=Path,
        default=Path("knowledge/normalized/prodecon/sections"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("knowledge/metadata/prodecon_integration_manifest.json"),
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_logging(get_settings().log_level)
    logger = logging.getLogger(__name__)

    stem = args.pdf.stem.lower().replace(" ", "-")
    markdown_path = args.normalized_dir / f"{stem}.md"
    metadata_path = args.metadata_dir / f"{stem}.json"

    try:
        if not markdown_path.exists() or not metadata_path.exists():
            processed = process_pdf(
                input_path=args.pdf,
                source_type=SourceType.PRODECON,
                output_dir=args.normalized_dir,
                metadata_dir=args.metadata_dir,
            )
            markdown_path = Path(processed.metadata.normalized_path)
            metadata_path = args.metadata_dir / f"{stem}.json"

        manifest = integrate_prodecon_sections(
            markdown_path=markdown_path,
            metadata_path=metadata_path,
            mapping_path=args.mapping,
            output_dir=args.sections_dir,
            manifest_path=args.manifest,
            overwrite=args.overwrite,
        )
    except (DocumentPipelineError, ProdeconIntegrationError, OSError) as exc:
        logger.error("%s", exc)
        return 1

    print(
        "OK: PRODECON integrado; "
        f"document_id={manifest.source_document_id}; "
        f"apartados={manifest.section_count}; "
        f"sha256={manifest.source_sha256}"
    )
    for section in manifest.sections:
        print(
            f"- {section.section_id}: páginas {section.page_start}-{section.page_end}; "
            f"módulo={section.module_key}; caracteres={section.character_count}"
        )
    if manifest.warnings:
        print("Advertencias:")
        for warning in manifest.warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
