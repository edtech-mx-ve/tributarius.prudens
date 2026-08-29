from __future__ import annotations

from pathlib import Path

from app.services.normative_temporal_runtime_guard import (
    TemporalRuntimeGuardError,
    load_temporal_runtime_guard,
)


def main() -> int:
    path = Path("knowledge/temporal/temporal_provenance_registry.json")
    try:
        guard = load_temporal_runtime_guard(path)
    except TemporalRuntimeGuardError as exc:
        print(f"ERROR: {exc}")
        return 1

    required = {"liva", "cpeum"}
    if not required.issubset(guard.blocked_documents):
        print(
            "ERROR: el guard temporal no bloquea todos los documentos "
            "prioritarios esperados."
        )
        return 1

    print("OK: Sprint 19I.15; guard temporal runtime cargado")
    print(f"- schema_version={guard.schema_version}")
    print(f"- source_sprint={guard.source_sprint}")
    print(f"- blocked_documents={','.join(sorted(guard.blocked_documents))}")
    print("- liva=blocked_unknown_fail_closed")
    print("- cpeum=blocked_unknown_fail_closed")
    print(
        "POLICY: el registro puede bloquear promociones normativas; "
        "no crea vigencia ni modifica metadatos RAG."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
