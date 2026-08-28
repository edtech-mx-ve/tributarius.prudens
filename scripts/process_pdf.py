from __future__ import annotations

import argparse
import logging
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.domain.documents import SourceType
from app.services.document_pipeline import DocumentPipelineError, process_pdf


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normaliza un PDF para el corpus RAG de Tributarius prudens."
    )
    parser.add_argument("--input", required=True, type=Path, help="Ruta al PDF original.")
    parser.add_argument(
        "--source-type",
        required=True,
        choices=[item.value for item in SourceType],
        help="Tipo de fuente documental.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directorio del Markdown normalizado. "
        "Por defecto: knowledge/normalized/<source-type>",
    )
    parser.add_argument(
        "--metadata-dir",
        type=Path,
        default=Path("knowledge/metadata"),
        help="Directorio para metadatos JSON.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    configure_logging(settings.log_level)

    source_type = SourceType(args.source_type)
    output_dir = args.output_dir or Path("knowledge/normalized") / source_type.value

    try:
        result = process_pdf(
            input_path=args.input,
            source_type=source_type,
            output_dir=output_dir,
            metadata_dir=args.metadata_dir,
        )
    except DocumentPipelineError as exc:
        logging.getLogger(__name__).error("%s", exc)
        return 1

    print("Documento procesado correctamente")
    print(f"ID: {result.metadata.document_id}")
    print(f"Fuente: {result.metadata.source_type.value}")
    print(f"Páginas: {result.metadata.stats.page_count}")
    print(f"Caracteres extraídos: {result.metadata.stats.extracted_characters}")
    print(f"Markdown: {result.metadata.normalized_path}")
    if result.metadata.warnings:
        print("Advertencias:")
        for warning in result.metadata.warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
