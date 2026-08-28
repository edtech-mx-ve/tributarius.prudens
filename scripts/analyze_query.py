from __future__ import annotations

import argparse
from pathlib import Path

from llm.errors import LLMError
from llm.providers.llama_cpp import LlamaCppProvider
from llm.providers.mock_query import MockQueryAnalyzerProvider
from llm.query_analyzer import QueryAnalyzer
from llm.structured_provider import StructuredMessageProvider


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analiza una consulta fiscal y devuelve una representación estructurada."
    )
    parser.add_argument("--query", required=True)
    parser.add_argument(
        "--provider",
        choices=["mock", "llama-cpp"],
        default="mock",
    )
    parser.add_argument("--model-path", type=Path, default=None)
    parser.add_argument("--n-ctx", type=int, default=4096)
    parser.add_argument("--max-tokens", type=int, default=700)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        provider: StructuredMessageProvider
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
            provider = MockQueryAnalyzerProvider()

        analysis = QueryAnalyzer(provider).analyze(args.query)
    except (ValueError, LLMError) as exc:
        print(f"ERROR: {exc}")
        return 1

    print(analysis.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
