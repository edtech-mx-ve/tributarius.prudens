from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import ValidationError

from app.domain.cbr import CBRQuery
from app.services.cbr_loader import CBRLoadError, load_cbr_cases_jsonl
from cbr.engine import retrieve_similar_cases

MAX_QUERY_BYTES = 64 * 1024


def load_query(path: Path) -> CBRQuery:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ValueError(f"No existe el archivo de consulta: {resolved.name}")
    if resolved.suffix.lower() != ".json":
        raise ValueError("La consulta CBR debe ser JSON.")
    if resolved.stat().st_size > MAX_QUERY_BYTES:
        raise ValueError("La consulta CBR supera 64 KB.")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        return CBRQuery.model_validate(payload)
    except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError("Consulta CBR inválida.") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recupera casos semejantes mediante CBR explicable."
    )
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--query-file", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        cases = load_cbr_cases_jsonl(args.cases)
        query = load_query(args.query_file)
        result = retrieve_similar_cases(query, cases)
    except (CBRLoadError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1

    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
