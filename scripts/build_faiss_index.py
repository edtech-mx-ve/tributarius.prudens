from __future__ import annotations

import argparse
import logging
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import configure_logging
from rag.embeddings.provider import DEFAULT_EMBEDDING_MODEL
from rag.indexing.builder import IndexBuildError, build_faiss_index


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Construye un índice FAISS CPU desde chunks jurídicos JSONL."
    )
    parser.add_argument(
        "--chunks",
        required=True,
        nargs="+",
        type=Path,
        help="Uno o más archivos JSONL generados por Sprint 3.",
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument(
        "--local-files-only",
        action="store_true",
        help="Impide descargas; exige que el modelo ya exista en caché local.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenera deliberadamente los artefactos conocidos del índice.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_logging(get_settings().log_level)

    try:
        manifest = build_faiss_index(
            args.chunks,
            args.output_dir,
            model_name=args.model,
            batch_size=args.batch_size,
            overwrite=args.overwrite,
            local_files_only=args.local_files_only,
        )
    except (IndexBuildError, ValueError) as exc:
        logging.getLogger(__name__).error("%s", exc)
        return 1

    print("Índice FAISS construido correctamente")
    print(f"Modelo: {manifest.model_name}")
    print(f"Chunks: {manifest.chunk_count}")
    print(f"Dimensión: {manifest.vector_dimension}")
    print(f"Métrica: {manifest.metric}")
    print(f"SHA-256 índice: {manifest.index_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
