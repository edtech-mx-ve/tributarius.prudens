from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from rag.embeddings.provider import EmbeddingError, SentenceTransformerEmbedder
from rag.evaluation.runtime_retrieval import (
    RetrievalEvalCase,
    RetrievalEvaluationSummary,
    evaluate_retrieval_case,
    summarize_evaluation,
)
from rag.retrieval.retriever import FaissRetriever, RetrievalError

_CASES = TypeAdapter(list[RetrievalEvalCase])


def _load_cases(path: Path) -> list[RetrievalEvalCase]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return _CASES.validate_python(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"No fue posible cargar {path}.") from exc


def _evaluate(
    index_dir: Path,
    cases: list[RetrievalEvalCase],
    embedder: SentenceTransformerEmbedder,
) -> RetrievalEvaluationSummary:
    retriever = FaissRetriever(index_dir, embedder)
    results = []
    for case in cases:
        retrieval = retriever.search(case.query, top_k=case.top_k)
        results.append(evaluate_retrieval_case(case, retrieval))
    return summarize_evaluation(results)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compara el baseline 19E contra el índice 19F."
    )
    parser.add_argument(
        "--baseline-dir",
        type=Path,
        default=Path("deployment/runtime_artifacts"),
    )
    parser.add_argument(
        "--candidate-dir",
        type=Path,
        default=Path("deployment/runtime_artifacts_19f"),
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("app/resources/retrieval_eval_cases.json"),
    )
    parser.add_argument("--local-files-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        cases = _load_cases(args.cases)
        embedder = SentenceTransformerEmbedder(
            device="cpu",
            local_files_only=args.local_files_only,
        )
        baseline = _evaluate(args.baseline_dir, cases, embedder)
        candidate = _evaluate(args.candidate_dir, cases, embedder)
    except (EmbeddingError, RetrievalError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1

    print("=== COMPARACIÓN 19E -> 19F.1 ===")
    rows = (
        ("Hit@1(any)", baseline.hit_at_1, candidate.hit_at_1),
        ("Hit@3(any)", baseline.hit_at_3, candidate.hit_at_3),
        ("Hit@K(any)", baseline.hit_at_k, candidate.hit_at_k),
        ("MRR(any)", baseline.mrr, candidate.mrr),
        (
            "PrimaryHit@1",
            baseline.primary_hit_at_1,
            candidate.primary_hit_at_1,
        ),
        (
            "PrimaryHit@3",
            baseline.primary_hit_at_3,
            candidate.primary_hit_at_3,
        ),
        (
            "PrimaryHit@K",
            baseline.primary_hit_at_k,
            candidate.primary_hit_at_k,
        ),
        ("PrimaryMRR", baseline.primary_mrr, candidate.primary_mrr),
        (
            "MeanUniqueDocs@K",
            baseline.mean_unique_documents_top_k,
            candidate.mean_unique_documents_top_k,
        ),
    )
    for name, before, after in rows:
        print(
            f"{name}: 19E={before:.3f}; 19F={after:.3f}; "
            f"delta={after - before:+.3f}"
        )

    print("\n=== CASOS 19F.1 ===")
    failed_primary = []
    for result in candidate.results:
        print(
            f"case={result.case_id}; "
            f"primary_rank={result.primary_first_rank}; "
            f"support_rank={result.supporting_first_rank}; "
            f"unique={result.unique_document_count}; "
            f"returned={','.join(result.returned_document_ids)}"
        )
        if not result.primary_hit_at_k:
            failed_primary.append(result.case_id)

    if failed_primary:
        print(
            "ATENCIÓN: fuentes principales ausentes en top-k: "
            + ",".join(failed_primary)
        )
        return 2

    if (
        candidate.primary_hit_at_k <= baseline.primary_hit_at_k
        or candidate.primary_mrr <= baseline.primary_mrr
    ):
        print(
            "ATENCIÓN: 19F no mejora simultáneamente PrimaryHit@K y "
            "PrimaryMRR respecto a 19E."
        )
        return 3

    print(
        "OK: todas las fuentes principales aparecen en top-k y "
        "19F mejora las métricas primarias."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
