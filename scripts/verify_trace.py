from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import ValidationError

from app.domain.traceability import CanonicalExecutionResult
from app.services.traceability import verify_canonical_integrity

MAX_TRACE_BYTES = 10 * 1024 * 1024


def load_trace(path: Path) -> CanonicalExecutionResult:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ValueError(f"No existe la trazabilidad: {resolved.name}")
    if resolved.suffix.lower() != ".json":
        raise ValueError("La trazabilidad debe usar formato JSON.")
    if resolved.stat().st_size > MAX_TRACE_BYTES:
        raise ValueError("La trazabilidad supera 10 MB.")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        return CanonicalExecutionResult.model_validate(payload)
    except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError("Archivo de trazabilidad inválido.") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verifica la integridad SHA-256 de un resultado canónico."
    )
    parser.add_argument("--trace", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        trace = load_trace(args.trace)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1

    if not verify_canonical_integrity(trace):
        print("ERROR: la huella canónica no coincide.")
        return 2

    print(f"OK: integridad verificada para {trace.folio}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
