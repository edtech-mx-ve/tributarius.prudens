from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.selective_semantic_candidate import (
    SelectiveSemanticCandidateError,
    audit_semantic_delta,
    build_rebased_staged_manifest,
)


def _write_manifest(
    path: Path,
    *,
    normalized: Path,
    metadata: Path,
    source_sha: str,
) -> None:
    payload = {
        "documents": [
            {
                "canonical_id": "lfdc",
                "filename": "LFDC.pdf",
                "source_sha256": source_sha,
                "normalized_path": str(normalized / "normativa" / "lfdc.md"),
                "metadata_path": str(metadata / "lfdc.json"),
                "legal_metadata_path": str(metadata / "legal" / "lfdc.json"),
            }
        ]
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_rebased_manifest_uses_staging_paths(tmp_path: Path) -> None:
    current_norm = tmp_path / "current" / "normalized"
    current_meta = tmp_path / "current" / "metadata"
    staged_norm = tmp_path / "staged" / "normalized"
    staged_meta = tmp_path / "staged" / "metadata"
    for path in (
        current_norm / "normativa",
        current_meta / "legal",
        staged_norm / "normativa",
        staged_meta / "legal",
    ):
        path.mkdir(parents=True)
    for path in (
        staged_norm / "normativa" / "lfdc.md",
        staged_meta / "lfdc.json",
        staged_meta / "legal" / "lfdc.json",
    ):
        path.write_text("x", encoding="utf-8")

    current_manifest = tmp_path / "current.json"
    staged_manifest = tmp_path / "staged.json"
    _write_manifest(
        current_manifest,
        normalized=current_norm,
        metadata=current_meta,
        source_sha="a" * 64,
    )
    _write_manifest(
        staged_manifest,
        normalized=tmp_path / "obsolete",
        metadata=tmp_path / "obsolete_meta",
        source_sha="b" * 64,
    )

    output = tmp_path / "rebased.json"
    result = build_rebased_staged_manifest(
        current_manifest_path=current_manifest,
        staged_manifest_path=staged_manifest,
        current_normalized_root=current_norm,
        current_metadata_root=current_meta,
        staged_normalized_root=staged_norm,
        staged_metadata_root=staged_meta,
        output_path=output,
    )
    row = result["documents"][0]
    assert Path(row["normalized_path"]) == (
        staged_norm / "normativa" / "lfdc.md"
    ).resolve()
    assert row["source_sha256"] == "b" * 64


def _chunk(document_id: str, chunk_id: str, text: str) -> str:
    return json.dumps(
        {
            "chunk_id": chunk_id,
            "text": text,
            "metadata": {"document_id": document_id},
        },
        ensure_ascii=False,
    )


def test_semantic_delta_allows_only_authorized_documents(
    tmp_path: Path,
) -> None:
    current = tmp_path / "current.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    current.write_text(
        "\n".join(
            [
                _chunk("cff", "cff-00001", "same"),
                _chunk("lfdc", "lfdc-001", "old"),
                _chunk("reg_liva_250914", "rliva-01", "old"),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    candidate.write_text(
        "\n".join(
            [
                _chunk("cff", "cff-00001", "same"),
                _chunk("lfdc", "lfdc-002", "new"),
                _chunk("reg_liva_250914", "rliva-02", "new"),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    deltas, unauthorized = audit_semantic_delta(current, candidate)
    changed = {item.document_id for item in deltas if item.changed}
    assert changed == {"lfdc", "reg_liva_250914"}
    assert unauthorized == []


def test_semantic_delta_blocks_unrelated_change(tmp_path: Path) -> None:
    current = tmp_path / "current.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    current.write_text(
        _chunk("cff", "cff-00001", "old") + "\n",
        encoding="utf-8",
    )
    candidate.write_text(
        _chunk("cff", "cff-00002", "new") + "\n",
        encoding="utf-8",
    )
    _, unauthorized = audit_semantic_delta(current, candidate)
    assert unauthorized == ["cff"]


def test_semantic_delta_blocks_document_set_change(tmp_path: Path) -> None:
    current = tmp_path / "current.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    current.write_text(
        _chunk("cff", "cff-00001", "same") + "\n",
        encoding="utf-8",
    )
    candidate.write_text(
        _chunk("lfdc", "lfdc-001", "same") + "\n",
        encoding="utf-8",
    )
    with pytest.raises(SelectiveSemanticCandidateError):
        audit_semantic_delta(current, candidate)
