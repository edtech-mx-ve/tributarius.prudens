from __future__ import annotations

import argparse
from pathlib import Path

from scripts.evaluate_runtime_retrieval_19g import _load_cases, evaluate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Evalúa el índice semántico v2 con el benchmark legal 19G.'
    )
    parser.add_argument(
        '--index-dir',
        type=Path,
        default=Path('deployment/runtime_artifacts_semantic_v2'),
    )
    parser.add_argument(
        '--cases',
        type=Path,
        default=Path('app/resources/retrieval_eval_cases.json'),
    )
    parser.add_argument(
        '--policy',
        type=Path,
        default=Path('app/resources/legal_retrieval_policy.json'),
    )
    parser.add_argument('--local-files-only', action='store_true')
    return parser.parse_args()


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
    except Exception as exc:
        print(f'ERROR: {exc}')
        return 1

    print('\n=== RETRIEVAL SEMANTIC V2 ===')
    print(f'cases={summary.case_count}')
    print(f'Hit@1(any)={summary.hit_at_1:.3f}')
    print(f'Hit@3(any)={summary.hit_at_3:.3f}')
    print(f'Hit@K(any)={summary.hit_at_k:.3f}')
    print(f'MRR(any)={summary.mrr:.3f}')
    print(f'PrimaryHit@1={summary.primary_hit_at_1:.3f}')
    print(f'PrimaryHit@3={summary.primary_hit_at_3:.3f}')
    print(f'PrimaryHit@K={summary.primary_hit_at_k:.3f}')
    print(f'PrimaryMRR={summary.primary_mrr:.3f}')
    print(f'MeanUniqueDocs@K={summary.mean_unique_documents_top_k:.3f}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
