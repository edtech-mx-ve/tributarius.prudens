from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.services.public_response_quality_19s_r16 import normalize_public_value

_SUSPICIOUS = ("Ã", "Â", "â€")


def _contains_mojibake(value: Any) -> bool:
    serialized = json.dumps(value, ensure_ascii=False, default=str)
    return any(marker in serialized for marker in _SUSPICIOUS)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gate local r16 para inspeccionar respuestas JSON públicas."
    )
    parser.add_argument("json_file", type=Path)
    args = parser.parse_args()

    if not args.json_file.is_file():
        print(f"ERROR: no existe {args.json_file}")
        return 2

    try:
        raw = json.loads(args.json_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: JSON inválido: {exc}")
        return 2

    normalized = normalize_public_value(raw)
    if _contains_mojibake(normalized):
        print("FAIL: permanecen marcadores de mojibake tras normalización.")
        return 1

    print("PASS: respuesta pública normalizable sin mojibake residual conocido.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
