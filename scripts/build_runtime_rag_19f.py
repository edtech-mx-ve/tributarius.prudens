from __future__ import annotations

import argparse
from pathlib import Path

from rag.indexing.builder import IndexBuildError, build_faiss_index


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Construye el índice FAISS de subchunks del Sprint 19F."
    )
    parser.add_argument(
        "--chunks",
        type=Path,
        default=Path("knowledge/retrieval_chunks/retrieval_chunks.jsonl"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("deployment/runtime_artifacts_19f"),
    )
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = build_faiss_index(
            [args.chunks],
            args.output_dir,
            batch_size=args.batch_size,
            overwrite=args.overwrite,
            local_files_only=args.local_files_only,
        )
    except IndexBuildError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("OK: Sprint 19F; índice FAISS de recuperación construido")
    print(f"- chunks={manifest.chunk_count}")
    print(f"- dimensión={manifest.vector_dimension}")
    print(f"- modelo={manifest.model_name}")
    print(f"- index.faiss={manifest.index_bytes} bytes")
    print(f"- chunks.jsonl={manifest.chunks_bytes} bytes")
    print(f"- tiempo={manifest.build_seconds:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
