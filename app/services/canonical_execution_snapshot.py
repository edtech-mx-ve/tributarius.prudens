from __future__ import annotations

import hashlib
import json

from app.domain.canonical_execution_snapshot import CanonicalExecutionSnapshot
from app.domain.traceability import CanonicalExecutionResult


class CanonicalExecutionSnapshotError(ValueError):
    """Error controlado al construir el snapshot canonico G.2."""


def canonical_execution_json(result: CanonicalExecutionResult) -> str:
    return json.dumps(
        result.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def build_canonical_execution_snapshot(
    result: CanonicalExecutionResult,
) -> CanonicalExecutionSnapshot:
    """Congela G.2 sin reejecutar ningun subsistema juridico."""

    source_sha256 = result.traceability.canonical_result_sha256
    if source_sha256 is None:
        raise CanonicalExecutionSnapshotError(
            "G.2 exige una ejecucion canonica con huella de integridad."
        )

    canonical_json = canonical_execution_json(result)
    snapshot_sha256 = hashlib.sha256(
        canonical_json.encode("utf-8")
    ).hexdigest()

    return CanonicalExecutionSnapshot(
        execution_id=result.execution_id,
        folio=result.folio,
        created_at_utc=result.created_at_utc,
        source_canonical_result_sha256=source_sha256,
        canonical_json=canonical_json,
        snapshot_sha256=snapshot_sha256,
    )
