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
from rag.retrieval.legal_hybrid import LegalHybridRetriever
from rag.retrieval.retriever import FaissRetriever, RetrievalError

_CASES = TypeAdapter(list[RetrievalEvalCase])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evalúa Sprint 19G sobre el índice 19F sin reconstruir FAISS."
    )
    parser.add_argument(
        "--index-dir",
        type=Path,
        default=Path("deployment/runtime_artifacts_19f"),
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("app/resources/retrieval_eval_cases.json"),
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path("app/resources/legal_retrieval_policy.json"),
    )
    parser.add_argument("--local-files-only", action="store_true")
    return parser.parse_args()


def _load_cases(path: Path) -> list[RetrievalEvalCase]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return _CASES.validate_python(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"No fue posible cargar {path}.") from exc


def evaluate(
    *,
    index_dir: Path,
    cases: list[RetrievalEvalCase],
    policy_path: Path,
    local_files_only: bool,
) -> RetrievalEvaluationSummary:
    embedder = SentenceTransformerEmbedder(
        device="cpu",
        local_files_only=local_files_only,
    )
    base = FaissRetriever(index_dir, embedder)
    retriever = LegalHybridRetriever.from_policy_file(base, policy_path)

    evaluated = []
    for case in cases:
        result = retriever.search(case.query, top_k=case.top_k)
        item = evaluate_retrieval_case(case, result)
        evaluated.append(item)
        print(
            f"case={item.case_id}; primary_rank={item.primary_first_rank}; "
            f"support_rank={item.supporting_first_rank}; "
            f"unique={item.unique_document_count}; "
            f"returned={','.join(item.returned_document_ids)}"
        )
    return summarize_evaluation(evaluated)


def main() -> int:
    args = parse_args()
    try:
        cases = _load_cases(args.cases)
        summary = evaluate(
            index_dir=args.index_dir,
            cases=cases,
            policy_path=args.policy,
            local_files_only=args.local_files_only,
        )
    except (EmbeddingError, RetrievalError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1

    print("\n=== RETRIEVAL 19G ===")
    print(f"cases={summary.case_count}")
    print(f"Hit@1(any)={summary.hit_at_1:.3f}")
    print(f"Hit@3(any)={summary.hit_at_3:.3f}")
    print(f"Hit@K(any)={summary.hit_at_k:.3f}")
    print(f"MRR(any)={summary.mrr:.3f}")
    print(f"PrimaryHit@1={summary.primary_hit_at_1:.3f}")
    print(f"PrimaryHit@3={summary.primary_hit_at_3:.3f}")
    print(f"PrimaryHit@K={summary.primary_hit_at_k:.3f}")
    print(f"PrimaryMRR={summary.primary_mrr:.3f}")
    print(f"MeanUniqueDocs@K={summary.mean_unique_documents_top_k:.3f}")
    print("OK: evaluación local Sprint 19G completada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
