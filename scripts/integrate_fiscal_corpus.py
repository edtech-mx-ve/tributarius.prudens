from __future__ import annotations

import argparse
import logging
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.fiscal_corpus_integration import (
    FiscalCorpusIntegrationError,
    integrate_fiscal_corpus,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19B: integra los 15 PDF restantes del corpus fiscal local "
            "(PRODECON fue integrado en Sprint 19A)."
        )
    )
    parser.add_argument("--corpus-dir", required=True, type=Path)
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path("app/resources/fiscal_corpus_15_catalog.json"),
    )
    parser.add_argument(
        "--normalized-root",
        type=Path,
        default=Path("knowledge/normalized"),
    )
    parser.add_argument(
        "--metadata-dir",
        type=Path,
        default=Path("knowledge/metadata"),
    )
    parser.add_argument(
        "--legal-metadata-dir",
        type=Path,
        default=Path("knowledge/metadata/legal"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("knowledge/metadata/fiscal_corpus_15_manifest.json"),
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_logging(get_settings().log_level)
    logger = logging.getLogger(__name__)

    try:
        manifest = integrate_fiscal_corpus(
            corpus_dir=args.corpus_dir,
            catalog_path=args.catalog,
            normalized_root=args.normalized_root,
            metadata_dir=args.metadata_dir,
            legal_metadata_dir=args.legal_metadata_dir,
            manifest_path=args.manifest,
            overwrite=args.overwrite,
        )
    except FiscalCorpusIntegrationError as exc:
        logger.error("%s", exc)
        return 1

    print(f"OK: corpus fiscal Sprint 19B integrado; documentos={manifest.document_count}")
    for item in manifest.documents:
        print(
            f"- {item.canonical_id}: {item.filename}; "
            f"páginas={item.page_count}; caracteres={item.extracted_characters}; "
            f"vacías={item.empty_pages}; sha256={item.source_sha256[:16]}..."
        )
    if manifest.warnings:
        print(f"Advertencias: {len(manifest.warnings)}")
        for warning in manifest.warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
