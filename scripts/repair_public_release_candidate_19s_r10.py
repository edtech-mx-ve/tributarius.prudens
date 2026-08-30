from __future__ import annotations

import argparse
from pathlib import Path

from app.services.public_release_integrity_19s_r10 import (
    PublicReleaseIntegrityError,
    repair_candidate,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sprint 19S-r10: repara y valida la integridad interna del candidato público."
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        summary = repair_candidate(args.source, args.output)
    except PublicReleaseIntegrityError as exc:
        print(f"ERROR: {exc}")
        return 3

    print("OK: Sprint 19S-r10; candidato reparado y validado localmente")
    print(f"- output={summary.output_path}")
    print(f"- bundle_sha256={summary.bundle_sha256}")
    print(f"- chunk_count={summary.chunk_count}")
    print(f"- chunks_sha256={summary.chunks_sha256}")
    print(f"- index_sha256={summary.index_sha256}")
    print(f"- index_ntotal={summary.index_ntotal}")
    print(f"- vector_dimension={summary.vector_dimension}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
