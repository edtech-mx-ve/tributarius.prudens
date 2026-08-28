from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.domain.traceability import CanonicalExecutionResult
from evaluation.dataset import EvaluationDatasetError, load_evaluation_dataset
from evaluation.evaluator import evaluate_integral
from evaluation.reporting import EvaluationReportError, export_evaluation_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluación integral offline.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--top-k", type=int, default=5)
    return parser.parse_args()


def load_results(manifest_path: Path) -> tuple[str, dict[str, CanonicalExecutionResult]]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    dataset_id = str(payload["dataset_id"])
    raw_results = payload["results"]
    if not isinstance(raw_results, dict):
        raise ValueError("results debe ser un objeto.")
    results: dict[str, CanonicalExecutionResult] = {}
    base = Path.cwd()
    for case_id, relative_path in raw_results.items():
        result_path = base / str(relative_path)
        result_payload = json.loads(result_path.read_text(encoding="utf-8"))
        results[str(case_id)] = CanonicalExecutionResult.model_validate(result_payload)
    return dataset_id, results


def main() -> int:
    args = parse_args()
    try:
        cases, digest = load_evaluation_dataset(args.dataset)
        dataset_id, results = load_results(args.manifest)
        report = evaluate_integral(
            cases,
            results,
            dataset_id=dataset_id,
            dataset_sha256=digest,
            top_k=args.top_k,
        )
        export_evaluation_report(report, args.output, overwrite=args.overwrite)
    except (
        EvaluationDatasetError,
        EvaluationReportError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        f"OK: {report.passed_case_count}/{report.case_count} casos; "
        f"overall_passed={report.overall_passed}."
    )
    return 0 if report.overall_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
