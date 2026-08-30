from __future__ import annotations

import argparse
import json
import urllib.request
from typing import Any, cast


def _post(
    base_url: str,
    timeout: float,
) -> dict[str, Any]:
    payload = {
        "query": (
            "Para el ejercicio fiscal 2026, ¿qué tasa de IVA debo aplicar "
            "a una operación gravada en México?"
        ),
        "mode": "taxpayer",
        "fiscal_year": 2026,
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/v1/consultations",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        decoded: Any = json.loads(response.read().decode("utf-8"))

    if not isinstance(decoded, dict):
        raise ValueError("La respuesta pública JSON debe ser un objeto.")

    return cast(dict[str, Any], decoded)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke r16E de calidad de evidencia pública."
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

    payload = _post(args.base_url, args.timeout)
    evidence = payload.get("result", {}).get("evidence", [])

    ref_ids = [
        str(item.get("ref_id") or "").strip()
        for item in evidence
        if isinstance(item, dict)
    ]
    nonempty_refs = [ref_id for ref_id in ref_ids if ref_id]
    duplicate_refs = len(nonempty_refs) - len(set(nonempty_refs))

    empty_cards = 0
    for item in evidence:
        if not isinstance(item, dict):
            continue
        visible = (
            item.get("ref_id"),
            item.get("document_id"),
            item.get("title"),
            item.get("unit"),
            item.get("snippet"),
        )
        if not any(str(value or "").strip() for value in visible):
            empty_cards += 1

    print(f"evidence_count={len(evidence)}")
    print(f"duplicate_ref_ids={duplicate_refs}")
    print(f"empty_cards={empty_cards}")

    if duplicate_refs or empty_cards:
        print("FAIL: evidencia pública aún contiene duplicados o tarjetas vacías.")
        return 1

    print("PASS: r16E evidencia pública visible limpia.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
