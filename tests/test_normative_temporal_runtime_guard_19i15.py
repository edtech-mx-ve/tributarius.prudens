from __future__ import annotations

import json
from pathlib import Path

from app.domain.chunks import ChunkMetadata, LegalChunkType, LegalHierarchy
from app.domain.documents import SourceType
from app.services.normative_rag_bridge import candidate_from_normative_hit
from app.services.normative_temporal_runtime_guard import (
    load_temporal_runtime_guard,
)
from rag.retrieval.models import RetrievalHit


def _write_registry(path: Path) -> None:
    payload = {
        "schema_version": "1.0",
        "source_sprint": "19I.13",
        "policy": "fail-closed",
        "entries": [],
        "coverage_gaps": [
            {
                "canonical_id": "liva",
                "gap_type": "document_wide_temporal_validity",
                "status": "unknown_fail_closed",
                "reason": "Sin vigencia documental verificada.",
            },
            {
                "canonical_id": "cpeum",
                "gap_type": "document_wide_temporal_validity",
                "status": "unknown_fail_closed",
                "reason": "Sin vigencia documental verificada.",
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _hit(document_id: str) -> RetrievalHit:
    return RetrievalHit(
        rank=1,
        score=0.9,
        chunk_id=f"{document_id}-art-1",
        text="Artículo 1. Texto normativo de prueba.",
        metadata=ChunkMetadata(
            document_id=document_id,
            source_type=SourceType.NORMATIVA,
            source_filename=f"{document_id}.md",
            chunk_index=1,
            chunk_type=LegalChunkType.ARTICLE,
            legal_identifier="Artículo 1",
            hierarchy=LegalHierarchy(article="Artículo 1"),
            source_sha256="a" * 64,
            version_label="2026",
            source_role="ley",
            document_type="ley",
            source_unit_type="article",
            source_unit_label="Artículo 1",
            effective_from="2026-01-01",
        ),
    )


def test_guard_loads_fail_closed_documents(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    _write_registry(registry)

    guard = load_temporal_runtime_guard(registry)

    assert guard.blocks_document("LIVA")
    assert guard.blocks_document("cpeum")
    assert not guard.blocks_document("lif_2026")


def test_guard_blocks_stale_temporal_metadata_for_liva(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    _write_registry(registry)
    guard = load_temporal_runtime_guard(registry)

    candidate = candidate_from_normative_hit(
        _hit("liva"),
        temporal_guard=guard,
    )

    assert candidate is None


def test_guard_preserves_non_blocked_temporally_valid_norm(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    _write_registry(registry)
    guard = load_temporal_runtime_guard(registry)

    candidate = candidate_from_normative_hit(
        _hit("lif_2026"),
        temporal_guard=guard,
    )

    assert candidate is not None
