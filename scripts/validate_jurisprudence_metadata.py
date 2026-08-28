from __future__ import annotations

import argparse
import sys
from pathlib import Path

from jurisprudence.loader import (
    JurisprudenceMetadataError,
    load_jurisprudence_metadata,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Valida metadatos jurisprudenciales JSONL."
    )
    parser.add_argument("--metadata", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        records = load_jurisprudence_metadata(args.metadata)
    except JurisprudenceMetadataError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    verified = sum(item.verified for item in records.values())
    print(
        f"OK: {len(records)} registros jurisprudenciales; "
        f"verified={verified}; sin persistir cambios."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
