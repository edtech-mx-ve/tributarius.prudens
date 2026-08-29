from __future__ import annotations

from app.services.normative_temporal_runtime_guard import TemporalRuntimeGuard


def test_temporal_guard_contract_blocks_priority_documents_only() -> None:
    guard = TemporalRuntimeGuard(
        blocked_documents=frozenset({"liva", "cpeum"}),
        schema_version="1.0",
        source_sprint="19I.13",
    )

    assert guard.blocks_document("LIVA")
    assert guard.blocks_document("CPEUM")
    assert not guard.blocks_document("lieps")
    assert not guard.blocks_document("lif_2026")
    assert not guard.blocks_document("rmf_2026")
