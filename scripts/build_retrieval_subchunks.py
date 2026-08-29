from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from rag.chunking.retrieval_subchunks import (
    RetrievalSubchunkError,
    build_retrieval_subchunks,
)
from rag.embeddings.provider import EmbeddingError, SentenceTransformerEmbedder
from rag.indexing.builder import IndexBuildError, load_chunks_jsonl, render_embedding_text


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Construye subchunks jurídicos trazables para Sprint 19F."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("deployment/runtime_artifacts/chunks.jsonl"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("knowledge/retrieval_chunks"),
    )
    parser.add_argument("--overlap-words", type=int, default=12)
    parser.add_argument("--expected-parents", type=int, default=3174)
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    output_file = output_dir / "retrieval_chunks.jsonl"
    manifest_file = output_dir / "retrieval_chunks_manifest.json"

    if (
        (output_file.exists() or manifest_file.exists())
        and not args.overwrite
    ):
        print("ERROR: la salida existe; use --overwrite para regenerarla.")
        return 1

    try:
        parents = load_chunks_jsonl(args.input)
        if len(parents) != args.expected_parents:
            raise ValueError(
                f"Se esperaban {args.expected_parents} padres y se cargaron "
                f"{len(parents)}."
            )

        embedder = SentenceTransformerEmbedder(
            device="cpu",
            local_files_only=args.local_files_only,
        )
        retrieval_chunks = build_retrieval_subchunks(
            parents,
            embedder,
            overlap_words=args.overlap_words,
        )

        token_counts = [
            embedder.count_tokens(render_embedding_text(chunk))
            for chunk in retrieval_chunks
        ]
    except (
        EmbeddingError,
        IndexBuildError,
        RetrievalSubchunkError,
        ValueError,
    ) as exc:
        print(f"ERROR: {exc}")
        return 1

    max_seq_length = embedder.max_seq_length
    risky = sum(count > max_seq_length for count in token_counts)
    if risky:
        print(f"ERROR: quedaron {risky} subchunks por encima del límite.")
        return 1

    parent_ids = {
        chunk.metadata.parent_chunk_id
        for chunk in retrieval_chunks
        if chunk.metadata.parent_chunk_id is not None
    }
    if len(parent_ids) != len(parents):
        print(
            "ERROR: no todos los chunks canónicos quedaron representados "
            "en los subchunks."
        )
        return 1

    by_document = Counter(
        chunk.metadata.document_id
        for chunk in retrieval_chunks
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = "\n".join(
        chunk.model_dump_json(exclude_none=True)
        for chunk in retrieval_chunks
    ) + "\n"

    with tempfile.TemporaryDirectory(
        prefix=".tributarius-subchunks-",
        dir=output_dir,
    ) as temp_name:
        temp_dir = Path(temp_name)
        temp_chunks = temp_dir / output_file.name
        temp_manifest = temp_dir / manifest_file.name
        temp_chunks.write_text(payload, encoding="utf-8")

        manifest = {
            "schema_version": "1.0",
            "created_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "strategy": "semantic_legal_v1",
            "model_name": embedder.model_name,
            "model_max_seq_length": max_seq_length,
            "parent_chunk_count": len(parents),
            "retrieval_chunk_count": len(retrieval_chunks),
            "parent_coverage": len(parent_ids),
            "overlap_words": args.overlap_words,
            "chunks_over_model_limit": risky,
            "max_rendered_tokens": max(token_counts),
            "min_rendered_tokens": min(token_counts),
            "mean_rendered_tokens": sum(token_counts) / len(token_counts),
            "input_sha256": _sha256_file(args.input.expanduser().resolve()),
            "retrieval_chunks_sha256": _sha256_file(temp_chunks),
            "by_document": dict(sorted(by_document.items())),
        }
        temp_manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temp_chunks, output_file)
        os.replace(temp_manifest, manifest_file)

    print("OK: Sprint 19F; subchunks de recuperación construidos")
    print(f"- padres={len(parents)}")
    print(f"- subchunks={len(retrieval_chunks)}")
    print(f"- cobertura_padres={len(parent_ids)}")
    print(f"- modelo={embedder.model_name}")
    print(f"- max_seq_length={max_seq_length}")
    print(f"- max_rendered_tokens={max(token_counts)}")
    print(f"- chunks_risk={risky}")
    print(f"- salida={output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
