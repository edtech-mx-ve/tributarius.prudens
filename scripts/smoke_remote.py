from __future__ import annotations

import argparse
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _get_json(url: str) -> tuple[int, dict[str, object]]:
    request = Request(url, headers={"User-Agent": "tributarius-prudens-smoke/1.0"})
    with urlopen(request, timeout=90) as response:
        body = json.loads(response.read().decode("utf-8"))
        return response.status, body


def _get_text(url: str) -> tuple[int, str]:
    request = Request(url, headers={"User-Agent": "tributarius-prudens-smoke/1.0"})
    with urlopen(request, timeout=90) as response:
        return response.status, response.read().decode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke HTTP remoto de Tributarius prudens.")
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    try:
        health_status, health = _get_json(f"{base}/health")
        home_status, home = _get_text(f"{base}/")
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"ERROR: smoke remoto falló: {exc}")
        return 1

    ok = (
        health_status == 200
        and health.get("service") == "tributarius-prudens"
        and health.get("status") in {"ok", "degraded"}
        and home_status == 200
        and "Tributarius prudens" in home
    )
    if not ok:
        print("ERROR: respuesta remota no satisface el contrato mínimo.")
        return 1

    print(
        "OK: despliegue remoto responde; "
        f"health={health.get('status')}; home=200."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
