from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pydantic import ValidationError

from rag.indexing.models import IndexManifest


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verifica integridad básica de un índice vectorial persistido."
    )
    parser.add_argument("--index-dir", required=True, type=Path)
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
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print(f"ERROR: manifiesto inválido: {exc}")
        return 1

    checks = {
        "index.faiss": (
            index_path.exists() and sha256_file(index_path) == manifest.index_sha256
        ),
        "chunks.jsonl": (
            chunks_path.exists() and sha256_file(chunks_path) == manifest.chunks_sha256
        ),
    }

    for name, valid in checks.items():
        print(f"{name}: {'OK' if valid else 'ERROR'}")

    if not all(checks.values()):
        return 1

    print("Integridad del índice: OK")
    print(f"Chunks declarados: {manifest.chunk_count}")
    print(f"Dimensión: {manifest.vector_dimension}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
