from __future__ import annotations

import argparse
import logging
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.corpus_chunking_service import CorpusChunkingError, build_legal_chunks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sprint 19C: estructura los 16 Markdown del corpus y genera chunks jurídicos."
    )
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path("app/resources/fiscal_corpus_15_catalog.json"),
    )
    parser.add_argument(
        "--fiscal-manifest",
        type=Path,
        default=Path("knowledge/metadata/fiscal_corpus_15_manifest.json"),
    )
    parser.add_argument(
        "--prodecon-manifest",
        type=Path,
        default=Path("knowledge/metadata/prodecon_integration_manifest.json"),
    )
    parser.add_argument(
        "--chunks",
        type=Path,
        default=Path("knowledge/chunks/chunks.jsonl"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("knowledge/chunks/chunking_manifest.json"),
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_logging(get_settings().log_level)
    logger = logging.getLogger(__name__)

    try:
        manifest = build_legal_chunks(
            project_root=args.project_root,
            catalog_path=args.catalog,
            fiscal_manifest_path=args.fiscal_manifest,
            prodecon_manifest_path=args.prodecon_manifest,
            chunks_path=args.chunks,
            manifest_path=args.manifest,
            overwrite=args.overwrite,
        )
    except CorpusChunkingError as exc:
        logger.error("%s", exc)
        return 1

    print(
        f"OK: Sprint 19C; documentos={manifest.document_count}; "
        f"chunks={manifest.chunk_count}; sha256={manifest.chunks_sha256[:16]}..."
    )
    for item in manifest.documents:
        print(
            f"- {item.canonical_id}: perfil={item.profile}; chunks={item.chunks}; "
            f"estructurados={item.structured_chunks}; fallback={item.fallback_chunks}; "
            f"caracteres={item.characters}"
        )
    if manifest.warnings:
        print(f"Advertencias: {len(manifest.warnings)}")
        for warning in manifest.warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
