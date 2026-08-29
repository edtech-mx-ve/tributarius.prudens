from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from rag.embeddings.provider import EmbeddingError, SentenceTransformerEmbedder
from rag.evaluation.runtime_retrieval import (
    RetrievalEvalCase,
    diagnose_chunk_lengths,
    evaluate_retrieval_case,
    summarize_evaluation,
)
from rag.indexing.builder import IndexBuildError, load_chunks_jsonl
from rag.retrieval.retriever import FaissRetriever, RetrievalError

CASES_ADAPTER = TypeAdapter(list[RetrievalEvalCase])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evalúa recuperación real de un índice RAG."
    )
    parser.add_argument(
        "--index-dir",
        type=Path,
        default=Path("deployment/runtime_artifacts"),
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("app/resources/retrieval_eval_cases.json"),
    )
    parser.add_argument("--label", default="RAG")
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--diagnose-lengths", action="store_true")
    parser.add_argument("--max-diagnostics", type=int, default=15)
    parser.add_argument("--min-hit-at-k", type=float, default=0.0)
    parser.add_argument("--min-primary-hit-at-k", type=float, default=0.0)
    return parser.parse_args()


def _load_cases(path: Path) -> list[RetrievalEvalCase]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return CASES_ADAPTER.validate_python(raw)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(
            f"No fue posible cargar casos de evaluación: {path}"
        ) from exc


def main() -> int:
    args = parse_args()
    for name, value in (
        ("--min-hit-at-k", args.min_hit_at_k),
        ("--min-primary-hit-at-k", args.min_primary_hit_at_k),
    ):
        if not 0.0 <= value <= 1.0:
            print(f"ERROR: {name} debe estar entre 0 y 1.")
            return 1
    if args.max_diagnostics < 1 or args.max_diagnostics > 100:
        print("ERROR: --max-diagnostics debe estar entre 1 y 100.")
        return 1

    try:
        cases = _load_cases(args.cases)
        embedder = SentenceTransformerEmbedder(
            local_files_only=args.local_files_only
        )
        retriever = FaissRetriever(args.index_dir, embedder)
    except (ValueError, RetrievalError, EmbeddingError) as exc:
        print(f"ERROR: {exc}")
        return 1

    evaluated = []
    for case in cases:
        try:
            result = retriever.search(case.query, top_k=case.top_k)
        except RetrievalError as exc:
            print(f"ERROR: caso={case.case_id}: {exc}")
            return 1
        item = evaluate_retrieval_case(case, result)
        evaluated.append(item)
        primary = ",".join(sorted(item.expected_primary_document_ids))
        support = ",".join(sorted(item.expected_supporting_document_ids)) or "-"
        returned = ",".join(item.returned_document_ids)
        print(
            f"case={item.case_id}; primary_rank={item.primary_first_rank}; "
            f"support_rank={item.supporting_first_rank}; primary={primary}; "
            f"support={support}; unique={item.unique_document_count}; "
            f"returned={returned}"
        )

    summary = summarize_evaluation(evaluated)
    print(f"\n=== RETRIEVAL {args.label} ===")
    print(f"cases={summary.case_count}")
    print(f"Hit@1(any)={summary.hit_at_1:.3f}")
    print(f"Hit@3(any)={summary.hit_at_3:.3f}")
    print(f"Hit@K(any)={summary.hit_at_k:.3f}")
    print(f"MRR(any)={summary.mrr:.3f}")
    print(f"PrimaryHit@1={summary.primary_hit_at_1:.3f}")
    print(f"PrimaryHit@3={summary.primary_hit_at_3:.3f}")
    print(f"PrimaryHit@K={summary.primary_hit_at_k:.3f}")
    print(f"PrimaryMRR={summary.primary_mrr:.3f}")
    print(
        "MeanUniqueDocs@K="
        f"{summary.mean_unique_documents_top_k:.3f}"
    )

    if args.diagnose_lengths:
        try:
            chunks = load_chunks_jsonl(args.index_dir / "chunks.jsonl")
            diagnostics = diagnose_chunk_lengths(chunks, embedder)
        except (IndexBuildError, EmbeddingError) as exc:
            print(f"ERROR: diagnóstico de longitud: {exc}")
            return 1

        risky = [item for item in diagnostics if item.truncation_risk]
        risky.sort(key=lambda item: item.token_ratio, reverse=True)
        per_document = Counter(item.document_id for item in risky)
        print("\n=== DIAGNÓSTICO DE TRUNCAMIENTO ===")
        print(f"model_max_seq_length={embedder.max_seq_length}")
        print(f"chunks_total={len(diagnostics)}")
        print(f"chunks_risk={len(risky)}")
        print(f"risk_ratio={len(risky) / len(diagnostics):.3f}")
        print(
            "risk_by_document="
            + json.dumps(
                per_document,
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        for length_diagnostic in risky[: args.max_diagnostics]:
            print(
                f"risk chunk={length_diagnostic.chunk_id}; "
                f"document={length_diagnostic.document_id}; "
                f"tokens={length_diagnostic.tokens}; "
                f"max={length_diagnostic.max_seq_length}; "
                f"ratio={length_diagnostic.token_ratio:.2f}; "
                f"chars={length_diagnostic.chars}"
            )

    if summary.hit_at_k < args.min_hit_at_k:
        print(
            f"ERROR: Hit@K(any)={summary.hit_at_k:.3f} < "
            f"umbral={args.min_hit_at_k:.3f}."
        )
        return 2
    if summary.primary_hit_at_k < args.min_primary_hit_at_k:
        print(
            f"ERROR: PrimaryHit@K={summary.primary_hit_at_k:.3f} < "
            f"umbral={args.min_primary_hit_at_k:.3f}."
        )
        return 3

    print(f"OK: evaluación RAG {args.label} completada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
