from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pydantic import ValidationError

from rag.indexing.faiss_store import FaissStoreError, FaissVectorStore
from rag.indexing.models import IndexManifest

EXPECTED_SPRINT_19D_CHUNKS = 3174


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _count_jsonl(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Valida integridad, cardinalidad y dimensión de artefactos RAG."
    )
    parser.add_argument(
        "--index-dir",
        type=Path,
        default=Path("deployment/runtime_artifacts"),
    )
    parser.add_argument(
        "--expected-chunks",
        type=int,
        default=EXPECTED_SPRINT_19D_CHUNKS,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    index_dir = args.index_dir.expanduser().resolve()
    manifest_path = index_dir / "manifest.json"
    index_path = index_dir / "index.faiss"
    chunks_path = index_dir / "chunks.jsonl"

    try:
        manifest = IndexManifest.model_validate(
            json.loads(manifest_path.read_text(encoding="utf-8"))
        )
        chunks_count = _count_jsonl(chunks_path)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print(f"ERROR: artefactos inválidos: {exc}")
        return 1

    if _sha256(index_path) != manifest.index_sha256:
        print("ERROR: SHA-256 de index.faiss no coincide.")
        return 1
    if _sha256(chunks_path) != manifest.chunks_sha256:
        print("ERROR: SHA-256 de chunks.jsonl no coincide.")
        return 1
    if chunks_count != manifest.chunk_count:
        print("ERROR: cardinalidad chunks.jsonl != manifest.chunk_count.")
        return 1
    if args.expected_chunks and chunks_count != args.expected_chunks:
        print(
            f"ERROR: Sprint 19D esperaba {args.expected_chunks} chunks; "
            f"obtuvo {chunks_count}."
        )
        return 1

    try:
        index = FaissVectorStore.read(index_path)
    except FaissStoreError as exc:
        print(f"ERROR: {exc}")
        return 1

    if int(index.ntotal) != manifest.chunk_count:
        print("ERROR: FAISS ntotal != manifest.chunk_count.")
        return 1
    if int(index.d) != manifest.vector_dimension:
        print("ERROR: FAISS dimension != manifest.vector_dimension.")
        return 1

    print("OK: artefactos RAG íntegros")
    print(f"- chunks={manifest.chunk_count}")
    print(f"- faiss_ntotal={int(index.ntotal)}")
    print(f"- dimensión={int(index.d)}")
    print(f"- modelo={manifest.model_name}")
    print(f"- index_sha256={manifest.index_sha256}")
    print(f"- chunks_sha256={manifest.chunks_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
