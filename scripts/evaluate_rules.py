from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.rule_engine import evaluate_rules
from app.services.rule_loader import load_rule_set


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evalúa reglas versionadas.")
    parser.add_argument("--rules", type=Path, required=True)
    parser.add_argument("--facts-json", required=True)
    parser.add_argument("--applicable-norm", action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        facts = json.loads(args.facts_json)
        if not isinstance(facts, dict):
            raise ValueError("facts-json debe ser un objeto JSON.")
        result = evaluate_rules(
            load_rule_set(args.rules),
            facts,
            set(args.applicable_norm),
        )
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1
    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
