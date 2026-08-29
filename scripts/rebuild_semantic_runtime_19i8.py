from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from app.services.semantic_runtime_rebuild import (
    SemanticRuntimeRebuildError,
    validate_semantic_runtime_inputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            'Sprint 19I.8: reconstruye subchunks y FAISS desde el corpus '
            'semántico promovido de 2981 padres.'
        )
    )
    parser.add_argument(
        '--canonical',
        type=Path,
        default=Path('knowledge/chunks/chunks_semantic_v2.jsonl'),
    )
    parser.add_argument(
        '--manifest',
        type=Path,
        default=Path('knowledge/chunks/chunks_semantic_v2_manifest.json'),
    )
    parser.add_argument(
        '--retrieval-dir',
        type=Path,
        default=Path('knowledge/retrieval_chunks_semantic_v2'),
    )
    parser.add_argument(
        '--runtime-dir',
        type=Path,
        default=Path('deployment/runtime_artifacts_semantic_v2'),
    )
    parser.add_argument('--expected-parents', type=int, default=2981)
    parser.add_argument('--batch-size', type=int, default=32)
    parser.add_argument('--local-files-only', action='store_true')
    parser.add_argument('--overwrite', action='store_true')
    parser.add_argument(
        '--stage',
        choices=('subchunks', 'index', 'all'),
        default='all',
    )
    return parser.parse_args()


def _run(command: list[str]) -> None:
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise SemanticRuntimeRebuildError(
            'Falló comando controlado: ' + ' '.join(command)
        )


def main() -> int:
    args = parse_args()
    try:
        inputs = validate_semantic_runtime_inputs(
            canonical_path=args.canonical,
            manifest_path=args.manifest,
            expected_parent_count=args.expected_parents,
        )

        retrieval_file = args.retrieval_dir / 'retrieval_chunks.jsonl'
        if args.stage in {'subchunks', 'all'}:
            command = [
                sys.executable,
                '-m',
                'scripts.build_retrieval_subchunks',
                '--input',
                str(inputs.canonical_path),
                '--output-dir',
                str(args.retrieval_dir),
                '--expected-parents',
                str(args.expected_parents),
            ]
            if args.local_files_only:
                command.append('--local-files-only')
            if args.overwrite:
                command.append('--overwrite')
            _run(command)

        if args.stage in {'index', 'all'}:
            command = [
                sys.executable,
                '-m',
                'scripts.build_runtime_rag_19f',
                '--chunks',
                str(retrieval_file),
                '--output-dir',
                str(args.runtime_dir),
                '--batch-size',
                str(args.batch_size),
            ]
            if args.local_files_only:
                command.append('--local-files-only')
            if args.overwrite:
                command.append('--overwrite')
            _run(command)

    except SemanticRuntimeRebuildError as exc:
        print(f'ERROR: {exc}')
        return 1

    print('OK: Sprint 19I.8; reconstrucción semántica RAG completada')
    print(f'- canonical={inputs.canonical_path}')
    print(f'- parents={inputs.expected_parent_count}')
    print(f'- canonical_sha256={inputs.canonical_sha256}')
    print(f'- retrieval_dir={args.retrieval_dir}')
    print(f'- runtime_dir={args.runtime_dir}')
    print(f'- stage={args.stage}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
