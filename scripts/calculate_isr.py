from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.domain.isr import ISRCalculationInput, ISRPeriod
from app.services.isr_tariff_loader import load_isr_tariff
from calculators.isr import calculate_isr


def decimal_arg(value: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError("Importe decimal inválido.") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calcula ISR de forma determinista.")
    parser.add_argument("--tariff", type=Path, required=True)
    parser.add_argument("--fiscal-year", type=int, required=True)
    parser.add_argument("--period", choices=[item.value for item in ISRPeriod], required=True)
    parser.add_argument("--gross-income", type=decimal_arg, required=True)
    parser.add_argument("--exempt-income", type=decimal_arg, default=Decimal("0"))
    parser.add_argument("--deductions", type=decimal_arg, default=Decimal("0"))
    parser.add_argument("--credits", type=decimal_arg, default=Decimal("0"))
    parser.add_argument("--normative-ref", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        tariff = load_isr_tariff(args.tariff)
        calculation_input = ISRCalculationInput(
            fiscal_year=args.fiscal_year,
            period=args.period,
            gross_income=args.gross_income,
            exempt_income=args.exempt_income,
            authorized_deductions=args.deductions,
            credits=args.credits,
            normative_ref=args.normative_ref,
        )
        result = calculate_isr(calculation_input, tariff)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1

    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
