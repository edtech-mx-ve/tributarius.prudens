from __future__ import annotations

import argparse
from pathlib import Path

from rag.embeddings.provider import SentenceTransformerEmbedder
from rag.retrieval.legal_hybrid import LegalHybridRetriever
from rag.retrieval.retriever import FaissRetriever, RetrievalError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Consulta manual del retriever híbrido jurídico Sprint 19G."
    )
    parser.add_argument("query")
    parser.add_argument(
        "--index-dir",
        type=Path,
        default=Path("deployment/runtime_artifacts_19f"),
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path("app/resources/legal_retrieval_policy.json"),
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--snippet-chars", type=int, default=300)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.top_k < 1 or args.top_k > 20:
        print("ERROR: --top-k debe estar entre 1 y 20.")
        return 1
    if args.snippet_chars < 80 or args.snippet_chars > 2000:
        print("ERROR: --snippet-chars debe estar entre 80 y 2000.")
        return 1

    try:
        embedder = SentenceTransformerEmbedder(
            device="cpu",
            local_files_only=args.local_files_only,
        )
        base = FaissRetriever(args.index_dir, embedder)
        retriever = LegalHybridRetriever.from_policy_file(base, args.policy)
        traced = retriever.search_with_trace(args.query, top_k=args.top_k)
    except RetrievalError as exc:
        print(f"ERROR: {exc}")
        return 1

    result = traced.result
    print(f"query={result.query}")
    print(f"mode={traced.query_mode}")
    print(f"routed={','.join(traced.routed_document_ids) or '-'}")
    print(
        f"semantic_candidates={traced.semantic_candidate_count}; "
        f"enriched={traced.enriched_candidate_count}; "
        f"returned={result.returned_count}"
    )

    for hit in result.hits:
        trace = traced.traces[hit.chunk_id]
        unit = hit.metadata.source_unit_label or hit.metadata.legal_identifier or "n/d"
        snippet = " ".join(hit.text.split())[: args.snippet_chars]
        print(
            f"[{hit.rank}] final={trace.final_score:.4f} "
            f"vector={trace.vector_score:.4f} lexical={trace.lexical_score:.4f} "
            f"route={trace.route_score:.1f} authority={trace.authority_score:.2f} "
            f"document={hit.metadata.document_id} unit={unit}"
        )
        print(f"    reasons={','.join(trace.reasons)}")
        print(f"    {snippet}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
