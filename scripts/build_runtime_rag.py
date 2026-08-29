from __future__ import annotations

import argparse
import logging
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import configure_logging
from rag.embeddings.provider import DEFAULT_EMBEDDING_MODEL
from rag.indexing.builder import IndexBuildError, build_faiss_index

EXPECTED_SPRINT_19D_CHUNKS = 3174


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Construye artefactos RAG de runtime desde knowledge/chunks/chunks.jsonl "
            "usando Sentence Transformers CPU + FAISS."
        )
    )
    parser.add_argument(
        "--chunks",
        type=Path,
        default=Path("knowledge/chunks/chunks.jsonl"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("deployment/runtime_artifacts"),
    )
    parser.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument(
        "--expected-chunks",
        type=int,
        default=EXPECTED_SPRINT_19D_CHUNKS,
        help="Puerta de calidad del corpus actual; use 0 para desactivarla.",
    )
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def _format_mib(value: int | None) -> str:
    if value is None:
        return "n/d"
    return f"{value / (1024 * 1024):.2f} MiB"


def main() -> int:
    args = parse_args()
    configure_logging(get_settings().log_level)

    if args.expected_chunks < 0:
        logging.getLogger(__name__).error("--expected-chunks no puede ser negativo.")
        return 1

    try:
        manifest = build_faiss_index(
            [args.chunks],
            args.output_dir,
            model_name=args.model,
            batch_size=args.batch_size,
            overwrite=args.overwrite,
            local_files_only=args.local_files_only,
        )
    except (IndexBuildError, ValueError) as exc:
        logging.getLogger(__name__).error("%s", exc)
        return 1

    if args.expected_chunks and manifest.chunk_count != args.expected_chunks:
        logging.getLogger(__name__).error(
            "Puerta 19D falló: esperados=%s, obtenidos=%s.",
            args.expected_chunks,
            manifest.chunk_count,
        )
        return 1

    print("OK: Sprint 19D; índice FAISS CPU construido")
    print(f"- modelo={manifest.model_name}")
    print(f"- chunks={manifest.chunk_count}")
    print(f"- dimensión={manifest.vector_dimension}")
    print(f"- métrica={manifest.metric}")
    print(f"- index.faiss={_format_mib(manifest.index_bytes)}")
    print(f"- chunks.jsonl={_format_mib(manifest.chunks_bytes)}")
    print(f"- tiempo={manifest.build_seconds:.2f}s")
    print(
        "- pico_memoria_python="
        f"{_format_mib(manifest.python_peak_memory_bytes)} "
        "(tracemalloc; no incluye toda la memoria nativa del modelo)"
    )
    print(f"- max_embedding_text_chars={manifest.max_embedding_text_chars}")
    print(f"- sha256_index={manifest.index_sha256}")
    print(f"- sha256_chunks={manifest.chunks_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
