from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.domain.documents import SourceType
from llm.errors import LLMError
from llm.provider import LLMProvider
from llm.providers.llama_cpp import LlamaCppProvider
from llm.providers.mock import MockLLMProvider
from llm.service import LlamaRAGService
from rag.embeddings.provider import SentenceTransformerEmbedder
from rag.retrieval.filters import RetrievalFilters
from rag.retrieval.retriever import FaissRetriever, RetrievalError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recupera evidencia y genera una explicación estructurada."
    )
    parser.add_argument("--index-dir", required=True, type=Path)
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--source-type",
        choices=[item.value for item in SourceType],
        default=None,
    )
    parser.add_argument("--fiscal-year", type=int, default=None)
    parser.add_argument(
        "--provider",
        choices=["mock", "llama-cpp"],
        default="mock",
    )
    parser.add_argument("--model-path", type=Path, default=None)
    parser.add_argument("--n-ctx", type=int, default=4096)
    parser.add_argument("--max-tokens", type=int, default=700)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--embedding-local-files-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = json.loads(
            (args.index_dir / "manifest.json").read_text(encoding="utf-8")
        )
        embedder = SentenceTransformerEmbedder(
            model_name=str(manifest["model_name"]),
            device="cpu",
            local_files_only=args.embedding_local_files_only,
        )
        retriever = FaissRetriever(args.index_dir, embedder)
        filters = RetrievalFilters(
            source_types=(
                {SourceType(args.source_type)} if args.source_type else set()
            ),
            fiscal_year=args.fiscal_year,
        )
        retrieval = retriever.search(
            args.query,
            top_k=args.top_k,
            filters=filters,
        )

        provider: LLMProvider

        if args.provider == "llama-cpp":
            if args.model_path is None:
                raise ValueError("--model-path es obligatorio con --provider llama-cpp.")
            provider = LlamaCppProvider(
                args.model_path,
                n_ctx=args.n_ctx,
                max_tokens=args.max_tokens,
                seed=args.seed,
            )
        else:
            provider = MockLLMProvider()

        explanation = LlamaRAGService(provider).explain(retrieval)
    except (OSError, KeyError, ValueError, RetrievalError, LLMError) as exc:
        print(f"ERROR: {exc}")
        return 1

    print(explanation.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
