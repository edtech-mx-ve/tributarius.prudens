from __future__ import annotations

import argparse
import logging
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.legal_chunker import ChunkingError, chunk_document


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera chunks jurídicos estructurados desde Markdown normalizado."
    )
    parser.add_argument("--markdown", required=True, type=Path)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--max-characters",
        type=int,
        default=6000,
        help="Longitud máxima aproximada por chunk (mínimo 500).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Permite regenerar deliberadamente un JSONL existente.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_logging(get_settings().log_level)

    try:
        report = chunk_document(
            markdown_path=args.markdown,
            metadata_path=args.metadata,
            output_path=args.output,
            overwrite=args.overwrite,
            max_characters=args.max_characters,
        )
    except ChunkingError as exc:
        logging.getLogger(__name__).error("%s", exc)
        return 1

    print("Chunking jurídico completado")
    print(f"Documento: {report.document_id}")
    print(f"Chunks: {report.chunk_count}")
    print(f"Páginas detectadas: {len(report.pages_seen)}")
    print("Distribución:")
    for chunk_type, count in report.by_type.items():
        print(f"- {chunk_type}: {count}")
    if report.warnings:
        print("Advertencias:")
        for warning in report.warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
