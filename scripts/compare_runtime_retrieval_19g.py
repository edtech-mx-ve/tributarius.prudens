from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from rag.embeddings.provider import (
    EmbeddingError,
    SentenceTransformerEmbedder,
)
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
        description="Compara 19F vectorial contra 19G híbrido jurídico."
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


def _evaluate_vector(
    retriever: FaissRetriever,
    cases: list[RetrievalEvalCase],
) -> RetrievalEvaluationSummary:
    results = [
        evaluate_retrieval_case(
            case,
            retriever.search(case.query, top_k=case.top_k),
        )
        for case in cases
    ]
    return summarize_evaluation(results)


def _evaluate_hybrid(
    retriever: LegalHybridRetriever,
    cases: list[RetrievalEvalCase],
) -> RetrievalEvaluationSummary:
    results = [
        evaluate_retrieval_case(
            case,
            retriever.search(case.query, top_k=case.top_k),
        )
        for case in cases
    ]
    return summarize_evaluation(results)


def _case_map(
    summary: RetrievalEvaluationSummary,
) -> dict[str, object]:
    return {item.case_id: item for item in summary.results}


def main() -> int:
    args = parse_args()
    try:
        cases = _load_cases(args.cases)
        embedder = SentenceTransformerEmbedder(
            device="cpu",
            local_files_only=args.local_files_only,
        )
        vector = FaissRetriever(args.index_dir, embedder)
        hybrid = LegalHybridRetriever.from_policy_file(vector, args.policy)
        baseline = _evaluate_vector(vector, cases)
        candidate = _evaluate_hybrid(hybrid, cases)
    except (EmbeddingError, RetrievalError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1

    print("=== COMPARACIÓN 19F.1 -> 19G ===")
    rows = (
        ("PrimaryHit@1", baseline.primary_hit_at_1, candidate.primary_hit_at_1),
        ("PrimaryHit@3", baseline.primary_hit_at_3, candidate.primary_hit_at_3),
        ("PrimaryHit@K", baseline.primary_hit_at_k, candidate.primary_hit_at_k),
        ("PrimaryMRR", baseline.primary_mrr, candidate.primary_mrr),
        ("Hit@K(any)", baseline.hit_at_k, candidate.hit_at_k),
        (
            "MeanUniqueDocs@K",
            baseline.mean_unique_documents_top_k,
            candidate.mean_unique_documents_top_k,
        ),
    )
    for metric_label, baseline_value, candidate_value in rows:
        print(
            f"{metric_label}: 19F={baseline_value:.3f}; "
            f"19G={candidate_value:.3f}; "
            f"delta={candidate_value - baseline_value:+.3f}"
        )

    baseline_cases = {item.case_id: item for item in baseline.results}
    candidate_cases = {item.case_id: item for item in candidate.results}

    regressions: list[str] = []
    for case_id, baseline_case in baseline_cases.items():
        candidate_case = candidate_cases[case_id]
        if (
            baseline_case.primary_hit_at_k
            and not candidate_case.primary_hit_at_k
        ):
            regressions.append(case_id)

    missing_primary = [
        case_id
        for case_id, item in candidate_cases.items()
        if not item.primary_hit_at_k
    ]

    print("\n=== CASOS 19G ===")
    for item in candidate.results:
        print(
            f"case={item.case_id}; primary_rank={item.primary_first_rank}; "
            f"support_rank={item.supporting_first_rank}; "
            f"returned={','.join(item.returned_document_ids)}"
        )

    if regressions:
        print(
            "ERROR: regresiones de fuente primaria en: "
            + ",".join(sorted(regressions))
        )
        return 2

    if missing_primary:
        print(
            "ERROR: fuentes primarias ausentes de top-k en: "
            + ",".join(sorted(missing_primary))
        )
        return 3

    if candidate.primary_hit_at_k <= baseline.primary_hit_at_k:
        print("ERROR: PrimaryHit@K no mejora respecto a 19F.1.")
        return 4

    if candidate.primary_mrr <= baseline.primary_mrr:
        print("ERROR: PrimaryMRR no mejora respecto a 19F.1.")
        return 5

    print(
        "OK: 19G recupera todas las fuentes primarias en top-k, "
        "mejora PrimaryHit@K y PrimaryMRR, y no introduce regresiones."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
