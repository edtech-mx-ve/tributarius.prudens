from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from typing import Any

_SUSPICIOUS = ("Ã", "Â", "â€")


def _fetch_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    try:
        ready = _fetch_json(f"{args.base_url.rstrip('/')}/ready")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"ERROR: no se pudo consultar /ready: {exc}")
        return 2

    serialized = json.dumps(ready, ensure_ascii=False)
    if any(marker in serialized for marker in _SUSPICIOUS):
        print("FAIL: /ready contiene mojibake conocido.")
        return 1
    print("PASS: /ready expone Unicode público sin mojibake conocido.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
