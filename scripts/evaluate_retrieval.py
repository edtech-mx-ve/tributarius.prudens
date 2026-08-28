from __future__ import annotations

import argparse
import json
from pathlib import Path

from rag.embeddings.provider import SentenceTransformerEmbedder
from rag.evaluation.dataset import load_evaluation_dataset
from rag.evaluation.metrics import EvaluationError, evaluate_retrieval
from rag.retrieval.retriever import FaissRetriever, RetrievalError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evalúa recuperación FAISS con un dataset JSONL etiquetado."
    )
    parser.add_argument("--index-dir", required=True, type=Path)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--local-files-only", action="store_true")
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
            local_files_only=args.local_files_only,
        )
        retriever = FaissRetriever(args.index_dir, embedder)
        cases = load_evaluation_dataset(args.dataset)
        expected = {
            case.query_id: case.relevant_chunk_ids for case in cases
        }
        retrieved = {
            case.query_id: [
                hit.chunk_id
                for hit in retriever.search(case.query, top_k=args.k).hits
            ]
            for case in cases
        }
        summary = evaluate_retrieval(expected, retrieved, k=args.k)
    except (OSError, KeyError, ValueError, RetrievalError, EvaluationError) as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"Consultas: {summary.query_count}")
    print(f"K: {summary.k}")
    print(f"Recall@K: {summary.recall_at_k:.4f}")
    print(f"Precision@K: {summary.precision_at_k:.4f}")
    print(f"MRR: {summary.mrr:.4f}")
    print(f"Hit Rate: {summary.hit_rate:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
