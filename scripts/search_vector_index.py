from __future__ import annotations

import argparse
from pathlib import Path

from app.domain.documents import SourceType
from rag.embeddings.provider import SentenceTransformerEmbedder
from rag.retrieval.filters import RetrievalFilters
from rag.retrieval.retriever import FaissRetriever, RetrievalError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Consulta un índice FAISS jurídico.")
    parser.add_argument("--index-dir", required=True, type=Path)
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--source-type",
        choices=[item.value for item in SourceType],
        default=None,
    )
    parser.add_argument("--fiscal-year", type=int, default=None)
    parser.add_argument("--local-files-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = args.index_dir / "manifest.json"
    try:
        import json
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        model_name = str(manifest["model_name"])
        embedder = SentenceTransformerEmbedder(
            model_name=model_name,
            device="cpu",
            local_files_only=args.local_files_only,
        )
        retriever = FaissRetriever(args.index_dir, embedder)
        filters = RetrievalFilters(
            source_types=(
                {SourceType(args.source_type)} if args.source_type else set()
            ),
            fiscal_year=args.fiscal_year,
        )
        result = retriever.search(
            args.query,
            top_k=args.top_k,
            filters=filters,
        )
    except (OSError, KeyError, ValueError, RetrievalError) as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"Consulta: {result.query}")
    print(f"Candidatos: {result.candidate_count}")
    print(f"Resultados: {result.returned_count}")
    for hit in result.hits:
        print(
            f"[{hit.rank}] score={hit.score:.4f} "
            f"chunk={hit.chunk_id} "
            f"fuente={hit.metadata.source_type.value} "
            f"página={hit.metadata.page_start}"
        )
        preview = " ".join(hit.text.split())[:240]
        print(f"    {preview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
