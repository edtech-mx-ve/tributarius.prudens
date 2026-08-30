from __future__ import annotations

import argparse
import json
from typing import Any

from scripts.e2e_public_response_r16d import CASES, post_json


def _normative_event(result: dict[str, Any]) -> dict[str, Any] | None:
    events = result.get("traceability", {}).get("events", [])
    for event in events:
        if isinstance(event, dict) and event.get("stage") == "normative":
            return event
    return None


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get("result")
    if not isinstance(result, dict):
        return {"payload": payload}

    uncertainties = result.get("uncertainties", [])
    return {
        "requires_human_review": result.get("requires_human_review"),
        "applicable_normative_refs_count": len(
            result.get("applicable_normative_refs", [])
        ),
        "primary_intent": result.get("traceability", {}).get(
            "primary_intent"
        ),
        "query_fiscal_year": result.get("traceability", {}).get(
            "query_fiscal_year"
        ),
        "uncertainties": uncertainties,
        "normative_event": _normative_event(result),
        "runtime": result.get("runtime"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diagnóstico focalizado r16D sin modificar estado."
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
    )
    args = parser.parse_args()

    targets = {
        "E2E-02-obligations",
        "E2E-03-isr-incomplete",
        "E2E-06-adversarial",
    }
    for case in CASES:
        if case.case_id not in targets:
            continue
        print(f"\n=== {case.case_id} ===")
        try:
            status, payload = post_json(
                args.base_url,
                case.payload,
                args.timeout,
            )
            print(f"status={status}")
            print(
                json.dumps(
                    _summary(payload),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        except Exception as exc:
            print(
                f"ERROR {type(exc).__name__}: "
                f"{exc!r}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
