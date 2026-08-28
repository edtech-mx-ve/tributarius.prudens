from __future__ import annotations

import argparse
from datetime import date

from app.domain.normative import NormativeApplicabilityRequest
from app.services.normative_engine import evaluate_normative_applicability


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evalúa vigencia temporal de una versión normativa."
    )
    parser.add_argument("--legal-unit-id", type=int, required=True)
    parser.add_argument("--version-label", required=True)
    parser.add_argument("--effective-from", type=date.fromisoformat, default=None)
    parser.add_argument("--effective-to", type=date.fromisoformat, default=None)
    parser.add_argument("--fiscal-year", type=int, default=None)
    parser.add_argument("--query-date", type=date.fromisoformat, required=True)
    parser.add_argument("--query-fiscal-year", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        request = NormativeApplicabilityRequest(
            legal_unit_id=args.legal_unit_id,
            version_label=args.version_label,
            effective_from=args.effective_from,
            effective_to=args.effective_to,
            fiscal_year=args.fiscal_year,
            query_date=args.query_date,
            query_fiscal_year=args.query_fiscal_year,
        )
        result = evaluate_normative_applicability(request)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1

    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
