from __future__ import annotations

import argparse
from pathlib import Path

from app.domain.documents import SourceType
from rag.embeddings.provider import SentenceTransformerEmbedder
from rag.retrieval.filters import RetrievalFilters
from rag.retrieval.retriever import FaissRetriever, RetrievalError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Consulta manual del RAG real de Tributarius prudens."
    )
    parser.add_argument("query")
    parser.add_argument("--index-dir", type=Path, default=Path("deployment/runtime_artifacts"))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--document-id", action="append", default=[])
    parser.add_argument(
        "--source-type",
        action="append",
        choices=[item.value for item in SourceType],
        default=[],
    )
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--snippet-chars", type=int, default=420)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.snippet_chars < 80 or args.snippet_chars > 4000:
        print("ERROR: --snippet-chars debe estar entre 80 y 4000.")
        return 1

    embedder = SentenceTransformerEmbedder(local_files_only=args.local_files_only)
    try:
        retriever = FaissRetriever(args.index_dir, embedder)
        filters = RetrievalFilters(
            document_ids=set(args.document_id),
            source_types={SourceType(value) for value in args.source_type},
        )
        result = retriever.search(args.query, top_k=args.top_k, filters=filters)
    except (RetrievalError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"query={result.query}")
    print(f"candidatos={result.candidate_count}; recuperados={result.returned_count}")
    for hit in result.hits:
        meta = hit.metadata
        unit = meta.source_unit_label or meta.legal_identifier or "n/d"
        snippet = " ".join(hit.text.split())[: args.snippet_chars]
        print(
            f"[{hit.rank}] score={hit.score:.4f} source={meta.source_type.value} "
            f"document={meta.document_id} unit={unit} pages={meta.page_start}-{meta.page_end}"
        )
        print(f"    {snippet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
