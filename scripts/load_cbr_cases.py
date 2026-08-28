from __future__ import annotations

import argparse
from pathlib import Path

from app.core.database import database_session
from app.repositories.cbr import CBRRepository
from app.services.cbr_loader import CBRLoadError, load_cbr_cases_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Valida o persiste un corpus CBR anonimizado."
    )
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Persiste en la base configurada. Sin esta bandera solo valida.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        cases = load_cbr_cases_jsonl(args.cases)
    except CBRLoadError as exc:
        print(f"ERROR: {exc}")
        return 1

    if not args.commit:
        print(f"OK: {len(cases)} casos CBR validados; no se persistieron cambios.")
        return 0

    try:
        with database_session() as session:
            repository = CBRRepository(session)
            for case in cases:
                repository.add_case(case)
    except (ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"OK: {len(cases)} casos CBR persistidos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
