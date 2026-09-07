from __future__ import annotations

import json

from app.services.canonical_execution_snapshot import (
    build_canonical_execution_snapshot,
)
from tests.test_block_g1_legal_consultation_report import _components


def _canonical():
    canonical, _, _ = _components()
    return canonical


def test_g2_freezes_existing_canonical_execution() -> None:
    canonical = _canonical()

    snapshot = build_canonical_execution_snapshot(canonical)

    assert snapshot.schema_version == "1.0"
    assert snapshot.execution_id == canonical.execution_id
    assert snapshot.folio == canonical.folio
    assert snapshot.created_at_utc == canonical.created_at_utc
    assert (
        snapshot.source_canonical_result_sha256
        == canonical.traceability.canonical_result_sha256
    )
    assert snapshot.source_results_already_computed is True
    assert snapshot.source_result_reexecuted is False
    assert snapshot.can_change_canonical_conclusion is False


def test_g2_snapshot_is_deterministic_for_same_execution() -> None:
    canonical = _canonical()

    first = build_canonical_execution_snapshot(canonical)
    second = build_canonical_execution_snapshot(canonical)

    assert first.canonical_json == second.canonical_json
    assert first.snapshot_sha256 == second.snapshot_sha256


def test_g2_snapshot_is_independent_from_later_source_mutation() -> None:
    canonical = _canonical()
    snapshot = build_canonical_execution_snapshot(canonical)

    original_json = snapshot.canonical_json

    canonical.query_analysis["g2_later_mutation"] = True

    assert snapshot.canonical_json == original_json
    assert "g2_later_mutation" not in json.loads(snapshot.canonical_json)


def test_g2_snapshot_preserves_traceability_identity() -> None:
    canonical = _canonical()
    snapshot = build_canonical_execution_snapshot(canonical)
    payload = json.loads(snapshot.canonical_json)

    assert payload["execution_id"] == snapshot.execution_id
    assert payload["folio"] == snapshot.folio
    assert (
        payload["traceability"]["canonical_result_sha256"]
        == snapshot.source_canonical_result_sha256
    )
